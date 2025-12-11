FROM python:3.12-slim

# Đặt thư mục làm việc trong container
WORKDIR /app

# Cài đặt uvicorn trước
RUN pip install --no-cache-dir uv

# Cài đặt môi trường Python
ENV UV_PYTHON=/usr/local/bin/python
ENV UV_PROJECT_ENVIRONMENT=/opt/venv
ENV PYTHONPATH=/app/src
# Sao chép các tệp pyproject.toml và uv.lock từ thư mục gốc vào thư mục làm việc trong container
COPY pyproject.toml uv.lock ./

# Thiết lập môi trường và đồng bộ các tệp phụ thuộc
RUN uv sync --frozen --no-dev --python $UV_PYTHON

# Cài đặt thư viện phụ thuộc vào container
ENV PATH="/opt/venv/bin:$PATH"

# Sao chép toàn bộ mã nguồn vào container
COPY . .

# Mở cổng 8000 để ứng dụng có thể truy cập
EXPOSE 8000

# Chạy ứng dụng FastAPI với uvicorn
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
