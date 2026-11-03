#!/bin/bash
# Fetches each codebase at the commit this study measured, as a shallow clone.
set -eu
cd "$(dirname "$0")"
mkdir -p work
fetch() {
  local name=$1 url=$2 commit=$3
  [ -d "work/$name" ] && return
  git init -q "work/$name"
  git -C "work/$name" fetch -q --depth 1 "$url" "$commit"
  git -C "work/$name" checkout -q FETCH_HEAD
}
fetch cpython https://github.com/python/cpython.git 3945eaf2fcd9cbc3f3061275bd29751c8b2e7d3b &
fetch django https://github.com/django/django.git b501b8493f31cf8cba31211d59b3b78642b8cb02 &
fetch mypy https://github.com/python/mypy.git ccbf32bd4c8d0246b47e43918d787e4a3c00acfa &
fetch saleor https://github.com/saleor/saleor.git dfbf13948fa0f71094555fcbbbe4ceccf9ce4eff &
fetch odoo https://github.com/odoo/odoo.git b0828a8702972e2759257c7dd3f8dd54a1e4a37d &
fetch homeassistant https://github.com/home-assistant/core.git 4317ce2630095d695a5de0aa644efcade0698699 &
fetch go https://github.com/golang/go.git 7b27665111926fad8dce05cff90616984acf9e81 &
fetch cockroach https://github.com/cockroachdb/cockroach.git d30c905fff79ef825adc96bcc647f1872a90f2ff &
fetch tidb https://github.com/pingcap/tidb.git e343a53e558f3eedcb7b8395e4856a90ba2a4ec8 &
fetch kubernetes https://github.com/kubernetes/kubernetes.git 8b2d0e51804e28ad83fb55c1863afda1001c84d5 &
fetch gitea https://github.com/go-gitea/gitea.git 12b20c7c9962e0be75912b290a0c5778799b0ad2 &
wait
