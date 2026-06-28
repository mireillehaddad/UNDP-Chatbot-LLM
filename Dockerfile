FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN pip install uv && uv sync --frozen --no-dev

COPY . .

ENV PYTHONPATH=/app
ENV PORT=8080

CMD ["uv", "run", "streamlit", "run", "src/chatbot/app.py", "--server.port=8080", "--server.address=0.0.0.0"]