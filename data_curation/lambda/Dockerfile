FROM python:3.11-slim

RUN pip install --no-cache-dir awslambdaric

WORKDIR /var/task

COPY requirements.txt .
RUN pip install --no-cache-dir --only-binary=:all: -r requirements.txt

COPY lambda_function.py .

ENTRYPOINT [ "/usr/local/bin/python", "-m", "awslambdaric" ]
CMD [ "lambda_function.lambda_handler" ]
