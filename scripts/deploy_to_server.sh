#!/bin/bash
# Deploy script to upload files and setup FastAPI on Google Cloud

PROJECT_ID="vertical-set-484818-f1"
INSTANCE_NAME="tim"
ZONE="us-east1-b"

echo "Uploading files to Google Cloud instance..."

# Upload all necessary files
gcloud compute scp --recurse app requirements.txt scripts/setup_server.sh \
    ${INSTANCE_NAME}:~/sundai/ \
    --zone=${ZONE} \
    --project=${PROJECT_ID}

echo "Files uploaded!"
echo ""
echo "Running setup on server..."

# Run the setup script
gcloud compute ssh ${INSTANCE_NAME} \
    --zone=${ZONE} \
    --project=${PROJECT_ID} \
    --command="chmod +x ~/sundai/setup_server.sh && ~/sundai/setup_server.sh"

echo ""
echo "Deployed"
