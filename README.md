# FraudDetection PS5
Detect Fraud in a large dataset
Use this schema in sampleData.json for transactions

You should create around 100 transactions with a few that are fraudulent in each batch. 
## High-Level Architecture

You want:

Input: Stream/list of transactions

Chunking: Split into batches of 20

Parallel LLM Calls: Send each batch to the model concurrently

Aggregation: Collect suspicious transactions

Single Write: Write all suspicious transactions to one file via a Tool
