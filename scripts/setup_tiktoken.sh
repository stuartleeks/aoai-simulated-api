#!/bin/bash  
  
# Create the tiktoken_cache folder  
folder_path="$(dirname -- "$0")/../src/aoai-simulated-api/tiktoken_cache"  
echo $folder_path  
  
mkdir -p $folder_path  
  
# Download the file from the URL  
echo "Downloading tiktoken encoding file..."  
url="https://openaipublic.blob.core.windows.net/encodings/cl100k_base.tiktoken"  
file_path="$folder_path/9b5ad71b2ce5302211f9c61530b329a4922fc6a4"  
curl -o $file_path $url  
  
echo "Finished tiktoken cache setup."  
