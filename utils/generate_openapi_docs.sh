#!/bin/bash

# This script generates OpenAPI documentation for the project.
FUZZBIN_API_JWT_SECRET="test-secret-for-openapi-gen-only" python3 utils/generate_openapi_docs.py