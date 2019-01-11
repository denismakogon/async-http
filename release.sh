#!/usr/bin/env bash


git checkout -b v${ASYNC_HTTP_VERSION}-stable
git push origin v${ASYNC_HTTP_VERSION}-stable
PBR_VERSION=${ASYNC_HTTP_VERSION} python setup.py sdist bdist_wheel
twine upload dist/async-http-${ASYNC_HTTP_VERSION}*
git checkout master
