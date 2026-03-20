FROM public.ecr.aws/lambda/python:3.10

# Copy requirements and install
COPY backend/requirements.txt ${LAMBDA_TASK_ROOT}/requirements.txt
RUN pip install --no-cache-dir -r ${LAMBDA_TASK_ROOT}/requirements.txt

# Copy backend code
COPY backend/main.py ${LAMBDA_TASK_ROOT}/
COPY backend/graph/ ${LAMBDA_TASK_ROOT}/graph/

# Copy data
COPY data/firm_profile.json ${LAMBDA_TASK_ROOT}/data/firm_profile.json
COPY data/chroma_db/ ${LAMBDA_TASK_ROOT}/data/chroma_db/

# When running in Lambda container, paths are relative to LAMBDA_TASK_ROOT
# Override env paths since .env won't exist in Lambda (use Lambda env vars instead)
ENV FIRM_PROFILE_PATH=data/firm_profile.json

# Lambda handler
CMD ["main.handler"]
