# Slurm REST API Documentation

Beautiful, interactive documentation for the Slurm REST API using Swagger UI.

## 🚀 Quick Start

### 1. Generate OpenAPI Specification

```bash
# Install dependencies
pip install -r requirements.txt

# Run the parser to generate openapi.json (default: localhost:6820)
python parse_api_docs.py

# Or specify a custom server URL
python parse_api_docs.py --server-url https://your-slurm-server.com:8080

# You can also specify a custom output file
python parse_api_docs.py --server-url https://your-slurm-server.com:8080 --output custom_openapi.json

# View all options
python parse_api_docs.py --help
```

### 2. View Documentation Locally

```bash
# Start a simple HTTP server
python -m http.server 8000

# Open in browser
open http://localhost:8000
```

## 📦 What's Included

- **parse_api_docs.py** - Python script that parses the Slurm HTML documentation and generates an OpenAPI 3.0 specification
- **index.html** - Beautiful Swagger UI interface for browsing the API
- **openapi.json** - Generated OpenAPI specification (created after running the parser)

## 🌐 Deployment

### GitHub Pages

1. Push this repository to GitHub
2. Go to Settings → Pages
3. Select the branch and root folder
4. Your documentation will be available at `https://username.github.io/repo-name/`

### Vercel

```bash
# Install Vercel CLI
npm i -g vercel

# Deploy
vercel
```

## 📚 Features

- ✨ Modern, responsive UI
- 🔍 Search and filter endpoints
- 🎨 Beautiful gradient header
- 📖 Interactive API explorer
- 🔐 Authentication documentation
- 🚀 Try-it-out functionality

## 🔗 Resources

- [Slurm Official Documentation](https://slurm.schedmd.com/rest_api.html)
- [Slurm GitHub Repository](https://github.com/SchedMD/slurm)
- [Swagger UI](https://swagger.io/tools/swagger-ui/)

## 📝 License

This documentation tool is provided as-is. Slurm is licensed under GPL.
