# FraudDetection PS5
Detect Fraud in a large dataset using an Express Web Server and Node.
Use this schema in sampleData.json for transactions
The user interface should allow monitoring of Agent and Tool calls 
and display of fraudulent transactions in near real time. 

You should create around 100 transactions with a few that are fraudulent in each batch. 
## High-Level Architecture

You probably want:

Input: Stream/list of transactions

Chunking: Split into batches of 20

Parallel Agent/LLM Calls: Send each batch to Openai model concurrently

Aggregation: Write suspicious transactions into a file  and to the UI via a suspiciousTransactions Tool


