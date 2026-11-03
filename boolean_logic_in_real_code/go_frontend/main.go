// Command go_frontend emits the boolean logic graph of every Go function in a
// codebase.
//
// Usage: go_frontend SOURCE_ROOT OUTPUT.jsonl [SUBDIR ...]
//
// Each output line describes one function in the intermediate form that
// analyze.py reads. See README.md for the form.
package main

import (
	"bufio"
	"bytes"
	"encoding/json"
	"fmt"
	"go/ast"
	"go/parser"
	"go/token"
	"io/fs"
	"os"
	"path/filepath"
	"regexp"
	"runtime"
	"sort"
	"strconv"
	"strings"
	"sync"
)

var generatedRE = regexp.MustCompile(`(?m)^// Code generated .* DO NOT EDIT\.$`)
var spaceRE = regexp.MustCompile(`\s+`)

var skipDirs = map[string]bool{
	"vendor": true, "testdata": true, ".git": true, "node_modules": true, "third_party": true,
}

type record struct {
	File          string   `json:"file"`
	Line          int      `json:"line"`
	Name          string   `json:"name"`
	Module        string   `json:"module"`
	Cls           *string  `json:"cls"`
	Method        bool     `json:"method"`
	Params        []string `json:"params"`
	Nres          int      `json:"nres"`
	PureCandidate bool     `json:"pure_candidate"`
	Nodes         [][]any  `json:"nodes"`
	Roots         []int    `json:"roots"`
	Rets          []int    `json:"rets"`
	Guards        []int    `json:"guards"`
	ReturnsBool   bool     `json:"returns_bool"`
}

type defKind int

const (
	defExpr defKind = iota
	defOpaque
	defZero
)

type def struct {
	kind defKind
	expr ast.Expr
}

type function struct {
	file       *fileContext
	params     []string
	paramIndex map[string]int
	boolNames  map[string]bool
	declared   map[string]bool
	defs       map[string][]def
	recvName   string
	nodes      [][]any
	memo       map[ast.Expr]int
	inProgress map[ast.Expr]int
	varNodes   map[string]int
	roots      []int
	rets       []int
	guards     []int
	nres       int
	simple     bool
}

type fileContext struct {
	rel     string
	src     []byte
	fset    *token.FileSet
	tf      *token.File
	imports map[string]string
	module  string
}

func (f *function) add(n []any) int {
	f.nodes = append(f.nodes, n)
	return len(f.nodes) - 1
}

func (f *function) text(e ast.Node) string {
	start := f.file.tf.Offset(e.Pos())
	end := f.file.tf.Offset(e.End())
	return spaceRE.ReplaceAllString(string(f.file.src[start:end]), " ")
}

func (f *function) refsParams(e ast.Node) bool {
	found := false
	ast.Inspect(e, func(n ast.Node) bool {
		if id, ok := n.(*ast.Ident); ok {
			if _, isParam := f.paramIndex[id.Name]; isParam {
				found = true
			}
		}
		return !found
	})
	return found
}

func (f *function) isLocal(name string) bool {
	return f.declared[name] && len(f.defs[name]) > 0
}

func isComparison(op token.Token) bool {
	switch op {
	case token.EQL, token.NEQ, token.LSS, token.GTR, token.LEQ, token.GEQ:
		return true
	}
	return false
}

func (f *function) booly(e ast.Expr, seen map[string]bool) bool {
	switch x := e.(type) {
	case *ast.ParenExpr:
		return f.booly(x.X, seen)
	case *ast.BinaryExpr:
		return x.Op == token.LAND || x.Op == token.LOR || isComparison(x.Op)
	case *ast.UnaryExpr:
		return x.Op == token.NOT
	case *ast.Ident:
		if x.Name == "true" || x.Name == "false" || f.boolNames[x.Name] {
			return true
		}
		if f.isLocal(x.Name) && !seen[x.Name] {
			seen[x.Name] = true
			defer delete(seen, x.Name)
			for _, d := range f.defs[x.Name] {
				if d.kind != defExpr || !f.booly(d.expr, seen) {
					return false
				}
			}
			return true
		}
	}
	return false
}

// isLogic reports whether e is itself boolean logic, so that == on it is xnor
// rather than a comparison.
func (f *function) isLogic(e ast.Expr) bool {
	switch x := e.(type) {
	case *ast.ParenExpr:
		return f.isLogic(x.X)
	case *ast.BinaryExpr:
		return x.Op == token.LAND || x.Op == token.LOR || isComparison(x.Op)
	case *ast.UnaryExpr:
		return x.Op == token.NOT
	case *ast.Ident:
		_, isParam := f.paramIndex[x.Name]
		return (f.isLocal(x.Name) || isParam) && x.Name != "true" && x.Name != "false" && f.booly(x, map[string]bool{})
	}
	return false
}

func (f *function) expr(e ast.Expr) int {
	if p, ok := e.(*ast.ParenExpr); ok {
		return f.expr(p.X)
	}
	if found, ok := f.memo[e]; ok {
		return found
	}
	if placeholder, ok := f.inProgress[e]; ok {
		// A local variable's definition reads the variable, as in
		// `done = done || x` in a loop, so the definition refers to itself
		// through a placeholder.
		if placeholder < 0 {
			placeholder = f.add([]any{"v", "", []int{}})
			f.inProgress[e] = placeholder
		}
		return placeholder
	}
	f.inProgress[e] = -1
	result := f.build(e)
	if placeholder := f.inProgress[e]; placeholder >= 0 {
		f.nodes[placeholder][2] = []int{result}
	}
	delete(f.inProgress, e)
	f.memo[e] = result
	return result
}

func (f *function) line(e ast.Node) int {
	return f.file.tf.Line(e.Pos())
}

func (f *function) stmt(op string, children []int, line int) int {
	return f.add([]any{"s", op, children, line})
}

func (f *function) leaf(e ast.Expr) int {
	return f.add([]any{"l", f.text(e), f.refsParams(e)})
}

func (f *function) build(e ast.Expr) int {
	switch x := e.(type) {
	case *ast.BinaryExpr:
		switch {
		case x.Op == token.LAND || x.Op == token.LOR:
			op := "and"
			if x.Op == token.LOR {
				op = "or"
			}
			return f.stmt(op, []int{f.expr(x.X), f.expr(x.Y)}, f.line(x))
		case (x.Op == token.EQL || x.Op == token.NEQ) && f.isLogic(x.X) && f.isLogic(x.Y):
			op := "xnor"
			if x.Op == token.NEQ {
				op = "xor"
			}
			return f.stmt(op, []int{f.expr(x.X), f.expr(x.Y)}, f.line(x))
		}
	case *ast.UnaryExpr:
		if x.Op == token.NOT {
			return f.stmt("not", []int{f.expr(x.X)}, f.line(x))
		}
	case *ast.Ident:
		if x.Name == "true" || x.Name == "false" {
			return f.add([]any{"k"})
		}
		if f.isLocal(x.Name) {
			return f.variable(x.Name)
		}
		if i, ok := f.paramIndex[x.Name]; ok {
			return f.add([]any{"p", i})
		}
	case *ast.BasicLit:
		return f.add([]any{"k"})
	case *ast.CallExpr:
		return f.call(x)
	}
	return f.leaf(e)
}

func (f *function) call(e *ast.CallExpr) int {
	recv := -1
	info := []string{"dyn", "", ""}
	fun := e.Fun
	if ix, ok := fun.(*ast.IndexExpr); ok {
		fun = ix.X
	}
	if ix, ok := fun.(*ast.IndexListExpr); ok {
		fun = ix.X
	}
	switch x := fun.(type) {
	case *ast.Ident:
		info = []string{"bare", x.Name, ""}
	case *ast.SelectorExpr:
		base, isIdent := x.X.(*ast.Ident)
		isParam := false
		if isIdent {
			_, isParam = f.paramIndex[base.Name]
		}
		switch {
		case isIdent && f.recvName != "" && base.Name == f.recvName:
			info = []string{"self", x.Sel.Name, ""}
			recv = f.expr(x.X)
		case isIdent && !f.declared[base.Name] && !isParam && f.file.imports[base.Name] != "":
			info = []string{"mod", x.Sel.Name, f.file.imports[base.Name]}
		default:
			info = []string{"attr", x.Sel.Name, ""}
			recv = f.expr(x.X)
		}
	}
	args := make([]int, 0, len(e.Args))
	for _, a := range e.Args {
		args = append(args, f.expr(a))
	}
	return f.add([]any{"c", f.text(e), f.refsParams(e), info, args, recv})
}

func (f *function) variable(name string) int {
	if found, ok := f.varNodes[name]; ok {
		return found
	}
	index := f.add([]any{"v", name, []int{}})
	f.varNodes[name] = index
	defs := []int{}
	if i, ok := f.paramIndex[name]; ok {
		defs = append(defs, f.add([]any{"p", i}))
	}
	for _, d := range f.defs[name] {
		switch d.kind {
		case defExpr:
			defs = append(defs, f.expr(d.expr))
		case defOpaque:
			defs = append(defs, f.add([]any{"l", "var:" + name, false}))
		case defZero:
			defs = append(defs, f.add([]any{"k"}))
		}
	}
	f.nodes[index][2] = defs
	return index
}

func identName(e ast.Expr) string {
	if id, ok := e.(*ast.Ident); ok && id.Name != "_" {
		return id.Name
	}
	return ""
}

func (f *function) addDef(name string, d def) {
	if name != "" {
		f.defs[name] = append(f.defs[name], d)
	}
}

func (f *function) collectDefs(body *ast.BlockStmt) {
	ast.Inspect(body, func(n ast.Node) bool {
		switch x := n.(type) {
		case *ast.AssignStmt:
			if x.Tok == token.DEFINE {
				for _, l := range x.Lhs {
					if name := identName(l); name != "" {
						f.declared[name] = true
					}
				}
			}
			if (x.Tok == token.DEFINE || x.Tok == token.ASSIGN) && len(x.Lhs) == len(x.Rhs) {
				for i, l := range x.Lhs {
					f.addDef(identName(l), def{defExpr, x.Rhs[i]})
				}
			} else {
				for _, l := range x.Lhs {
					f.addDef(identName(l), def{kind: defOpaque})
				}
			}
		case *ast.ValueSpec:
			for i, nameIdent := range x.Names {
				name := identName(nameIdent)
				if name == "" {
					continue
				}
				f.declared[name] = true
				if t, ok := x.Type.(*ast.Ident); ok && t.Name == "bool" {
					f.boolNames[name] = true
				}
				switch {
				case len(x.Values) == len(x.Names):
					f.addDef(name, def{defExpr, x.Values[i]})
				case len(x.Values) == 0:
					f.addDef(name, def{kind: defZero})
				default:
					f.addDef(name, def{kind: defOpaque})
				}
			}
		case *ast.RangeStmt:
			for _, e := range []ast.Expr{x.Key, x.Value} {
				if name := identName(e); name != "" {
					if x.Tok == token.DEFINE {
						f.declared[name] = true
					}
					f.addDef(name, def{kind: defOpaque})
				}
			}
		case *ast.IncDecStmt:
			f.addDef(identName(x.X), def{kind: defOpaque})
		case *ast.TypeSwitchStmt:
			if a, ok := x.Assign.(*ast.AssignStmt); ok {
				for _, l := range a.Lhs {
					if name := identName(l); name != "" {
						f.declared[name] = true
						f.addDef(name, def{kind: defOpaque})
					}
				}
			}
		case *ast.FuncLit:
			for _, field := range x.Type.Params.List {
				for _, nameIdent := range field.Names {
					if name := identName(nameIdent); name != "" {
						f.declared[name] = true
						f.addDef(name, def{kind: defOpaque})
					}
				}
			}
		}
		return true
	})
}

func isSimple(stmts []ast.Stmt) bool {
	for _, s := range stmts {
		switch x := s.(type) {
		case *ast.ReturnStmt, *ast.AssignStmt, *ast.DeclStmt:
		case *ast.IfStmt:
			if !isSimple(x.Body.List) {
				return false
			}
			if x.Else != nil {
				if b, ok := x.Else.(*ast.BlockStmt); ok && !isSimple(b.List) {
					return false
				} else if !ok && !isSimple([]ast.Stmt{x.Else}) {
					return false
				}
			}
		case *ast.BlockStmt:
			if !isSimple(x.List) {
				return false
			}
		default:
			return false
		}
	}
	return true
}

func (f *function) walk(body *ast.BlockStmt) {
	var visit func(n ast.Node, inClosure bool)
	visit = func(root ast.Node, inClosure bool) {
		ast.Inspect(root, func(n ast.Node) bool {
			switch x := n.(type) {
			case *ast.FuncLit:
				if x != root {
					visit(x.Body, true)
					return false
				}
			case *ast.IfStmt:
				f.roots = append(f.roots, f.expr(x.Cond))
				if !inClosure && (containsReturn(x.Body) || containsReturn(x.Else)) {
					f.guards = append(f.guards, f.roots[len(f.roots)-1])
				}
			case *ast.ForStmt:
				if x.Cond != nil {
					f.roots = append(f.roots, f.expr(x.Cond))
					if !inClosure && containsReturn(x.Body) {
						f.guards = append(f.guards, f.roots[len(f.roots)-1])
					}
				}
			case *ast.SwitchStmt:
				returns := !inClosure && containsReturn(x.Body)
				if x.Tag == nil {
					for _, c := range x.Body.List {
						for _, e := range c.(*ast.CaseClause).List {
							f.roots = append(f.roots, f.expr(e))
							if returns {
								f.guards = append(f.guards, f.roots[len(f.roots)-1])
							}
						}
					}
				} else if returns {
					// Which case runs depends on how the tag compares to each
					// case value; each such comparison is one input.
					for _, c := range x.Body.List {
						for _, e := range c.(*ast.CaseClause).List {
							f.guards = append(f.guards, f.add([]any{"l", f.text(x.Tag) + " == " + f.text(e), f.refsParams(x.Tag) || f.refsParams(e)}))
						}
					}
				}
			case *ast.TypeSwitchStmt:
				if !inClosure && containsReturn(x.Body) {
					for _, c := range x.Body.List {
						for _, e := range c.(*ast.CaseClause).List {
							f.guards = append(f.guards, f.add([]any{"l", f.text(x.Assign) + " is " + f.text(e), f.refsParams(x.Assign)}))
						}
					}
				}
			case *ast.ReturnStmt:
				if !inClosure && f.nres == 1 && len(x.Results) == 1 {
					f.rets = append(f.rets, f.expr(x.Results[0]))
				}
			case *ast.BinaryExpr:
				if x.Op == token.LAND || x.Op == token.LOR ||
					((x.Op == token.EQL || x.Op == token.NEQ) && f.isLogic(x.X) && f.isLogic(x.Y)) {
					f.expr(x)
				}
			case *ast.UnaryExpr:
				if x.Op == token.NOT {
					f.expr(x)
				}
			}
			return true
		})
	}
	visit(body, false)
}

func containsReturn(n ast.Node) bool {
	if n == nil {
		return false
	}
	found := false
	ast.Inspect(n, func(m ast.Node) bool {
		switch m.(type) {
		case *ast.ReturnStmt:
			found = true
		case *ast.FuncLit:
			return false
		}
		return !found
	})
	return found
}

func typeName(e ast.Expr) string {
	switch x := e.(type) {
	case *ast.StarExpr:
		return typeName(x.X)
	case *ast.IndexExpr:
		return typeName(x.X)
	case *ast.IndexListExpr:
		return typeName(x.X)
	case *ast.Ident:
		return x.Name
	}
	return ""
}

func analyzeFunc(ctx *fileContext, d *ast.FuncDecl) record {
	f := &function{
		file: ctx, paramIndex: map[string]int{}, boolNames: map[string]bool{},
		declared: map[string]bool{}, defs: map[string][]def{}, memo: map[ast.Expr]int{}, inProgress: map[ast.Expr]int{},
		varNodes: map[string]int{}, simple: isSimple(d.Body.List),
	}
	rec := record{File: ctx.rel, Line: ctx.fset.Position(d.Pos()).Line, Name: d.Name.Name, Module: ctx.module}
	addParam := func(name string, t ast.Expr) {
		if name == "" {
			name = "_"
		}
		if name != "_" {
			f.paramIndex[name] = len(f.params)
			f.declared[name] = true
		}
		f.params = append(f.params, name)
		if id, ok := t.(*ast.Ident); ok && id.Name == "bool" {
			f.boolNames[name] = true
		}
	}
	if d.Recv != nil && len(d.Recv.List) == 1 {
		field := d.Recv.List[0]
		name := ""
		if len(field.Names) == 1 {
			name = field.Names[0].Name
		}
		f.recvName = name
		cls := typeName(field.Type)
		rec.Cls = &cls
		rec.Method = true
		addParam(name, field.Type)
	}
	allBool := len(d.Type.Params.List) > 0
	for _, field := range d.Type.Params.List {
		if id, ok := field.Type.(*ast.Ident); !ok || id.Name != "bool" {
			allBool = false
		}
		if len(field.Names) == 0 {
			addParam("", field.Type)
		}
		for _, n := range field.Names {
			addParam(n.Name, field.Type)
		}
	}
	returnsBool := false
	if d.Type.Results != nil {
		for _, field := range d.Type.Results.List {
			count := len(field.Names)
			if count == 0 {
				count = 1
			}
			f.nres += count
			for _, n := range field.Names {
				f.declared[n.Name] = true
				f.addDef(n.Name, def{kind: defZero})
			}
			if id, ok := field.Type.(*ast.Ident); ok && id.Name == "bool" {
				returnsBool = true
			}
		}
	}
	f.collectDefs(d.Body)
	f.walk(d.Body)
	rec.Params = f.params
	rec.Nres = f.nres
	rec.PureCandidate = allBool && f.simple && returnsBool && f.nres == 1 && len(f.rets) > 0
	rec.Nodes = f.nodes
	rec.Roots = f.roots
	rec.Rets = f.rets
	rec.Guards = f.guards
	rec.ReturnsBool = returnsBool && f.nres == 1
	if rec.Guards == nil {
		rec.Guards = []int{}
	}
	if rec.Roots == nil {
		rec.Roots = []int{}
	}
	if rec.Rets == nil {
		rec.Rets = []int{}
	}
	if rec.Nodes == nil {
		rec.Nodes = [][]any{}
	}
	return rec
}

type modInfo struct {
	dir  string
	path string
}

var modCache sync.Map

func findModule(dir string) modInfo {
	if v, ok := modCache.Load(dir); ok {
		return v.(modInfo)
	}
	var info modInfo
	data, err := os.ReadFile(filepath.Join(dir, "go.mod"))
	if err == nil {
		path := ""
		for line := range strings.SplitSeq(string(data), "\n") {
			if rest, ok := strings.CutPrefix(strings.TrimSpace(line), "module "); ok {
				path = strings.Trim(strings.TrimSpace(rest), `"`)
				break
			}
		}
		info = modInfo{dir, path}
	} else if parent := filepath.Dir(dir); parent != dir {
		info = findModule(parent)
	}
	modCache.Store(dir, info)
	return info
}

var versionRE = regexp.MustCompile(`^v[0-9]+$`)

func importName(path string) string {
	parts := strings.Split(path, "/")
	last := parts[len(parts)-1]
	if versionRE.MatchString(last) && len(parts) > 1 {
		last = parts[len(parts)-2]
	}
	if i := strings.IndexAny(last, ".-"); i >= 0 {
		if strings.HasPrefix(last, "go-") {
			last = last[3:]
		} else {
			last = last[:i]
		}
	}
	return last
}

func analyzeFile(root, rel string) ([]record, string) {
	path := filepath.Join(root, rel)
	src, err := os.ReadFile(path)
	if err != nil {
		panic(err)
	}
	if pkg := bytes.Index(src, []byte("\npackage ")); pkg >= 0 && generatedRE.Match(src[:pkg]) {
		return nil, "generated"
	}
	fset := token.NewFileSet()
	file, err := parser.ParseFile(fset, path, src, parser.SkipObjectResolution)
	if err != nil {
		return nil, "error"
	}
	mod := findModule(filepath.Dir(path))
	relDir, _ := filepath.Rel(mod.dir, filepath.Dir(path))
	module := mod.path + "/" + filepath.ToSlash(relDir)
	switch {
	case relDir == ".":
		module = mod.path
	case mod.path == "std":
		module = filepath.ToSlash(relDir)
	}
	ctx := &fileContext{rel: rel, src: src, fset: fset, tf: fset.File(file.Pos()), imports: map[string]string{}, module: module}
	for _, imp := range file.Imports {
		p, _ := strconv.Unquote(imp.Path.Value)
		name := importName(p)
		if imp.Name != nil {
			name = imp.Name.Name
		}
		ctx.imports[name] = p
	}
	var out []record
	for _, decl := range file.Decls {
		if d, ok := decl.(*ast.FuncDecl); ok && d.Body != nil {
			out = append(out, analyzeFunc(ctx, d))
		}
	}
	return out, "ok"
}

func main() {
	root, output, subdirs := os.Args[1], os.Args[2], os.Args[3:]
	if len(subdirs) == 0 {
		subdirs = []string{"."}
	}
	var files []string
	for _, sub := range subdirs {
		err := filepath.WalkDir(filepath.Join(root, sub), func(p string, d fs.DirEntry, err error) error {
			if err != nil {
				return err
			}
			if d.IsDir() {
				if skipDirs[d.Name()] {
					return filepath.SkipDir
				}
				return nil
			}
			if strings.HasSuffix(p, ".go") && !strings.HasSuffix(p, "_test.go") {
				rel, _ := filepath.Rel(root, p)
				files = append(files, rel)
			}
			return nil
		})
		if err != nil {
			panic(err)
		}
	}
	sort.Strings(files)
	results := make([]chan []byte, len(files))
	for i := range results {
		results[i] = make(chan []byte, 1)
	}
	var generated, parseErrors, mu = 0, 0, sync.Mutex{}
	jobs := make(chan int)
	for range runtime.GOMAXPROCS(0) {
		go func() {
			for i := range jobs {
				recs, status := analyzeFile(root, files[i])
				mu.Lock()
				switch status {
				case "error":
					parseErrors++
				case "generated":
					generated++
				}
				mu.Unlock()
				var buf bytes.Buffer
				enc := json.NewEncoder(&buf)
				for _, r := range recs {
					if err := enc.Encode(r); err != nil {
						panic(err)
					}
				}
				results[i] <- buf.Bytes()
			}
		}()
	}
	go func() {
		for i := range files {
			jobs <- i
		}
		close(jobs)
	}()
	out, err := os.Create(output)
	if err != nil {
		panic(err)
	}
	w := bufio.NewWriter(out)
	for i := range files {
		if _, err := w.Write(<-results[i]); err != nil {
			panic(err)
		}
	}
	if err := w.Flush(); err != nil {
		panic(err)
	}
	if err := out.Close(); err != nil {
		panic(err)
	}
	fmt.Fprintf(os.Stderr, "files=%d generated_skipped=%d parse_errors=%d\n", len(files), generated, parseErrors)
}
