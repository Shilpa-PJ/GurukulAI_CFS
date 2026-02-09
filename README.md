# AI-Gurukul
Repository to store the code and data for both the use cases which are being built in AI Gurukul
The Repository currently contains the sqlite db file along with the code to host a local server and connect to the DB, with the API endpoints required currently

# Steps to Follow

1. Download the files and store it in the same folder
2. pip install the following libraries -> fastapi & uvicorn (command to run -> pip install fastapi uvicorn)
3. run the server in localhost (command to run ->uvicorn main:app --reload)
4. Once the server starts running the following API endpoints are exposed :  
   1."/api/accounts/{account}/balance"  
   2."/api/accounts/{account}/statements/adhoc"  
   3."/api/accounts/{account}/statements/current"  
   4."/api/accounts/{account}/transactions"  
5. These APIs can be tested in Postman (example : http://127.0.0.1:8000/api/accounts/1065000025/transactions)
   
