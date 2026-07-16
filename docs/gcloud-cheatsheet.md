# gcloud CLI Cheat Sheet

Quick reference for common gcloud commands used in this project.

## Authentication

```bash
# Login with your Google account
gcloud auth login

# Set up Application Default Credentials (ADC) for local development
gcloud auth application-default login

# ADC with specific scopes (e.g., for Maps/Places API)
gcloud auth application-default login --scopes="https://www.googleapis.com/auth/cloud-platform"

# Check current authenticated account
gcloud auth list

# Revoke credentials
gcloud auth revoke

# Print access token (useful for debugging)
gcloud auth print-access-token
```

## Project Management

```bash
# List all projects
gcloud projects list

# Set default project
gcloud config set project PROJECT_ID

# Get current project
gcloud config get-value project

# Describe a project
gcloud projects describe PROJECT_ID
```

## IAM & Permissions

```bash
# List IAM policy for a project
gcloud projects get-iam-policy PROJECT_ID

# List IAM policy in table format
gcloud projects get-iam-policy PROJECT_ID --format="table(bindings.role,bindings.members)"

# Add IAM binding
gcloud projects add-iam-policy-binding PROJECT_ID \
    --member="user:email@example.com" \
    --role="roles/editor"

# Remove IAM binding
gcloud projects remove-iam-policy-binding PROJECT_ID \
    --member="user:email@example.com" \
    --role="roles/editor"
```

## API Keys

```bash
# List all API keys in a project
gcloud services api-keys list --project=PROJECT_ID

# Get the actual key string value
gcloud services api-keys get-key-string KEY_NAME --project=PROJECT_ID
# Example: gcloud services api-keys get-key-string projects/123/locations/global/keys/abc-123

# Get full details of an API key (including restrictions)
gcloud services api-keys describe KEY_NAME --project=PROJECT_ID

# Create a new API key
gcloud services api-keys create --display-name="My API Key" --project=PROJECT_ID

# Update API key restrictions
gcloud services api-keys update KEY_NAME \
    --api-target=service=places.googleapis.com \
    --project=PROJECT_ID
```

## Billing

```bash
# Check if billing is enabled for a project
gcloud billing projects describe PROJECT_ID

# List billing accounts you have access to
gcloud billing accounts list

# Get details of a billing account
gcloud billing accounts describe BILLING_ACCOUNT_ID
# Example: gcloud billing accounts describe 019A01-CB7F0C-FFBE42

# Link a project to a billing account
gcloud billing projects link PROJECT_ID --billing-account=BILLING_ACCOUNT_ID
```

## APIs & Services

```bash
# List enabled APIs for current project
gcloud services list --enabled

# List all available APIs
gcloud services list --available

# Enable an API
gcloud services enable places.googleapis.com

# Disable an API
gcloud services disable places.googleapis.com

# Check if a specific API is enabled
gcloud services list --enabled --filter="name:places.googleapis.com"
```

## Service Accounts

```bash
# List service accounts
gcloud iam service-accounts list

# Create a service account
gcloud iam service-accounts create SA_NAME \
    --display-name="Display Name"

# Create and download a key for a service account
gcloud iam service-accounts keys create key.json \
    --iam-account=SA_NAME@PROJECT_ID.iam.gserviceaccount.com

# List keys for a service account
gcloud iam service-accounts keys list \
    --iam-account=SA_NAME@PROJECT_ID.iam.gserviceaccount.com
```

## Configuration

```bash
# View all configurations
gcloud config configurations list

# Create a new configuration
gcloud config configurations create CONFIG_NAME

# Switch to a configuration
gcloud config configurations activate CONFIG_NAME

# Set a property
gcloud config set compute/region us-central1

# View current configuration
gcloud config list
```

## Debugging & Troubleshooting

```bash
# Get detailed info about current auth
gcloud auth describe ACCOUNT_EMAIL

# Check ADC credentials location
echo $GOOGLE_APPLICATION_CREDENTIALS

# Default ADC location (if env var not set)
cat ~/.config/gcloud/application_default_credentials.json

# Test API access with curl using access token
curl -H "Authorization: Bearer $(gcloud auth print-access-token)" \
     -H "X-Goog-User-Project: PROJECT_ID" \
     "https://places.googleapis.com/v1/places:searchText"

# Verbose output for debugging
gcloud --verbosity=debug COMMAND
```

## Common Output Formats

```bash
# JSON output
gcloud projects list --format=json

# Table output
gcloud projects list --format="table(projectId,name,projectNumber)"

# Value only (for scripting)
gcloud config get-value project

# Custom formatting
gcloud projects list --format="value(projectId)"
```

## Quick Diagnostics Script

```bash
# Run this to diagnose common issues
echo "=== Current Account ==="
gcloud auth list --filter=status:ACTIVE --format="value(account)"

echo "=== Current Project ==="
gcloud config get-value project

echo "=== Billing Status ==="
gcloud billing projects describe $(gcloud config get-value project) 2>/dev/null || echo "Could not fetch billing info"

echo "=== Enabled APIs (Maps/Places related) ==="
gcloud services list --enabled --filter="name:places OR name:maps" --format="table(name)"

echo "=== API Keys ==="
gcloud services api-keys list --format="table(displayName,restrictions.apiTargets[0].service)"
```

## Environment Variables

```bash
# Point to a service account key file
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account-key.json"

# Set project for ADC
export GOOGLE_CLOUD_PROJECT="my-project-id"

# Or use gcloud to set quota project in ADC
gcloud auth application-default set-quota-project PROJECT_ID
```

## Useful Links

- [gcloud Reference](https://cloud.google.com/sdk/gcloud/reference)
- [Places API (New) Documentation](https://developers.google.com/maps/documentation/places/web-service/op-overview)
- [Authentication Overview](https://cloud.google.com/docs/authentication)
- [IAM Roles Reference](https://cloud.google.com/iam/docs/understanding-roles)
