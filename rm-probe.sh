python3 - <<'PY'
import os, ssl, sys
print("python:", sys.version.split()[0])
print("REQUESTS_CA_BUNDLE as seen in python:", os.environ.get("REQUESTS_CA_BUNDLE"))
print("SSL_CERT_FILE as seen in python:", os.environ.get("SSL_CERT_FILE"))
c = ssl.create_default_context()
certs = c.get_ca_certs()
print("python default trust certs:", len(certs))
print("run CA in python default trust:", any("AOSCP Interception CA" in str(x.get("subject","")) for x in certs))
try:
    import boto
    from boto import cacerts
    p = os.path.join(os.path.dirname(cacerts.__file__), "cacerts.txt")
    body = open(p).read()
    print("boto", boto.__version__, "cacerts.txt certs:", body.count("BEGIN CERTIFICATE"))
    import subprocess
    print("run CA in boto2 cacerts.txt:", "AOSCP Interception CA" in subprocess.run(
        ["python3","-c","import sys,ssl;print(1)"],capture_output=True,text=True).stdout or None)
except Exception as e:
    print("boto probe error:", e)
PY
echo "-- run CA present in the discovered stores? --"
for f in $(python3 /opt/amazon/sandbox-common/bin/sandbox-ca.py discover 2>/dev/null); do
  n=$(grep -c 'BEGIN CERTIFICATE' "$f" 2>/dev/null || echo NA)
  h=$(python3 - "$f" <<'PY'
import sys,ssl,re
p=sys.argv[1]
try:
    data=open(p,'rb').read()
except Exception as e:
    print("unreadable"); raise SystemExit
import subprocess
PY
)
  echo "  $f certs=$n"
done
