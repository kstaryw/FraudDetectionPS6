# FraudDetection PS-6
The goal is to detect Fraud in a large dataset that is larger than the context window. This means we need to break the data into chunks and process these chunks in parallel. 
The schema in sampleData.json gives some examples of transactions with some most likely fraudulent. We will start with a demo using only 100 transactions but these chould be chunked into 5 batches of 20 and processed in parallel.
The user interface should allow monitoring of Agent and Tool calls so you can check what is happening. You should accumulate fraudulent transactions into a single file. You can view this accumulator as keeping "state" of the app.  
Your UI should display the fraudulent transactions in near real time. 

You should create around 100 transactions with a few that are fraudulent in each batch. 
## High-Level Architecture

You probably want the following:

Input: Stream/list of transactions

Chunking: Split into batches of 20

Parallel Agent/LLM Calls: Send each batch to Openai model concurrently

Aggregation: Write suspicious transactions into the file and to the UI via a suspiciousTransactions Tool


