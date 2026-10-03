FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    chrony rsyslog tftpd-hpa iputils-ping procps tcpdump \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /srv/tftp /var/log/network /var/spool/rsyslog /var/lib/chrony /var/log/chrony

COPY chrony.conf    /etc/chrony/chrony.conf
COPY rsyslog.conf   /etc/rsyslog.conf
COPY entrypoint.sh  /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
