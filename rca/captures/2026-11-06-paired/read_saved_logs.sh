#!/bin/sh
export LESSSECURE=1
exec /usr/bin/less -R -X -P "저장 기록 재생 · q" -- "$@"
