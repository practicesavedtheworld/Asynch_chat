FROM python:3.9

COPY . .

RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# optional
# CMD ['python', 'server.py'] 
CMD ['python', 'client.py']
