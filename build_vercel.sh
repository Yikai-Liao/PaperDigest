#!/bin/bash
git config --global url.https://github.com/.insteadOf git@github.com:
git submodule update --init --recursive
cd website
pnpm install
pnpm run build