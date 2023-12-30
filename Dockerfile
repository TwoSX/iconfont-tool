FROM ubuntu:22.04

RUN apt-get update -y && \
    apt-get -y install python3 python3-pip

# 设置 Python 3 和 Pip3 为默认
RUN ln -s /usr/bin/python3 /usr/bin/python
ENV PYTHON=python3

RUN apt-get install -y fontforge python3-fontforge

RUN apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

ENV PYTHONPATH=/usr/local/lib/python3/dist-packages/

WORKDIR /app

COPY . .

RUN pip install -r requirements.txt

EXPOSE 8080

CMD ["python", "main.py"]
