#!/usr/bin/env bash
echo -e "$(date -Iseconds)\t$1\t$2" >> "$(dirname "$0")/../memory/usage.log"