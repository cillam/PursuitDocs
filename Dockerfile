FROM public.ecr.aws/lambda/python:3.10

# Copy requirements and install
COPY backend/backend_requirements.txt ${LAMBDA_TASK_ROOT}/requirements.txt
RUN pip install --upgrade pip && pip install --no-cache-dir -r ${LAMBDA_TASK_ROOT}/requirements.txt

# Copy backend code
COPY backend/main.py ${LAMBDA_TASK_ROOT}/
COPY backend/graph/ ${LAMBDA_TASK_ROOT}/graph/

# Chroma DB and firm profiles are loaded from S3 at runtime — do not copy here

ENV ENVIRONMENT=production

CMD ["main.handler"]
