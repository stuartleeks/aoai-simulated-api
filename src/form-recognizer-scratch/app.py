import os
from azure.core.credentials import AzureKeyCredential
from azure.ai.formrecognizer import DocumentAnalysisClient

endpoint = os.environ["AZURE_FORM_RECOGNIZER_ENDPOINT"]
key = os.environ["AZURE_FORM_RECOGNIZER_KEY"]

credential = AzureKeyCredential(key)
document_analysis_client = DocumentAnalysisClient(endpoint, credential)

with open("./src/form-recognizer-scratch/Detailed Grocery Payment Receipt Samples.pdf", "rb") as f:
    poller = document_analysis_client.begin_analyze_document("prebuilt-receipt", f)

result = poller.result()
print("Poller result: ", result)

for idx, receipt in enumerate(result.documents):
    print("--------Recognizing receipt #{}--------".format(idx + 1))
    receipt_type = receipt.fields.get("ReceiptType")
    if receipt_type:
        print("Receipt Type:", receipt_type.value)
    merchant_name = receipt.fields.get("MerchantName")
    if merchant_name:
        print("Merchant Name:", merchant_name.value)
    transaction_date = receipt.fields.get("TransactionDate")
    if transaction_date:
        print("Transaction Date:", transaction_date.value)
    print("--------------------------------------")

# [END recognize_receipts_from_url]
