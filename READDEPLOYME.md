Build image
```
 gcloud builds submit `
  --tag northamerica-northeast1-docker.pkg.dev/undp-project-documents/undp-pipeline/undp-chatbot-new:latest
```

Deploy

```
 gcloud run deploy undp-chatbot-new `
  --image northamerica-northeast1-docker.pkg.dev/undp-project-documents/undp-pipeline/undp-chatbot-new:latest `
  --region northamerica-northeast1 `
  --platform managed `
  --allow-unauthenticated `
  --memory 2Gi `
  --cpu 1 `
  --set-env-vars "PROJECT_ID=undp-project-documents,REGION=northamerica-northeast1,BUCKET_NAME=undp-documents-llm-prod,BIGQUERY_DATASET=undp_rag_prod,BIGQUERY_TABLE=document_embeddings_prod,EMBEDDING_MODEL=gemini-embedding-001,GENERATION_MODEL=gemini-2.5-flash"
  
```
Get url
```
  gcloud run services describe undp-chatbot-new `
  --region northamerica-northeast1 `
  --format "value(status.url)"
  ```


  URL:

  ```
https://undp-chatbot-new-cprvqspw5q-nn.a.run.app/

  ```

 