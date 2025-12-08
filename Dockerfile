# Use the official Azure Functions Python base image
FROM mcr.microsoft.com/azure-functions/python:4-python3.11

# Set working dir to functions app root expected by the image
ENV AzureWebJobsScriptRoot=/home/site/wwwroot \
    AzureFunctionsJobHost__Logging__Console__IsEnabled=true

WORKDIR /home/site/wwwroot

# Copy application files
COPY . /home/site/wwwroot

# Upgrade pip and install requirements
RUN python -m pip install --upgrade pip \
    && pip install --no-cache-dir -r /home/site/wwwroot/requirements.txt

# Expose port (Functions host listens on 80 inside container)
EXPOSE 80

# Default command provided by the base image will start the Functions host
# (no CMD override required). If you want to customize, uncomment below:
# CMD ["/azure-functions-host/Microsoft.Azure.WebJobs.Script.WebHost"]
