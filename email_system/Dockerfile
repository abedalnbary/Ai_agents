FROM python:3.12-slim
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Works from both monorepo and standalone:
#   monorepo:   docker build -f email_system/Dockerfile -t email-service email_system/
#   standalone: docker build -t email-service .
# Either way the build context root is email_system/, so we copy everything
# into /app/email_system/ so "from email_system.xxx" resolves correctly.
COPY . ./email_system/

ENV EMAIL_API_URL=http://localhost:8000
EXPOSE 8000

CMD ["uvicorn", "email_system.api.email_api:app", "--host", "0.0.0.0", "--port", "8000"]
