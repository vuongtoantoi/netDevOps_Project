log() { echo "[$(date '+%F %T')] $*"; }

chmod 777 /srv/tftp                                   
chronyd -d -x &                                       
rsyslogd -n &                                         
in.tftpd -L -c -s -u tftp -a 0.0.0.0:69 /srv/tftp &   
log "chronyd / rsyslogd / in.tftpd da chay"


wait -n
log "ERROR: mot dich vu da thoat -> restart container"
exit 1
