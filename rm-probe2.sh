python3 - <<'PY'
import os, ssl, sys, subprocess
print("python:", sys.version.split()[0])
print("REQUESTS_CA_BUNDLE seen in python:", os.environ.get("REQUESTS_CA_BUNDLE"))
print("SSL_CERT_FILE seen in python:", os.environ.get("SSL_CERT_FILE"))
c = ssl.create_default_context()
certs = c.get_ca_certs()
print("python default trust certs:", len(certs))
print("run CA in python default trust:", any("AOSCP Interception CA" in str(x.get("subject","")) for x in certs))
try:
    import boto, boto.connection
    p = boto.connection.DEFAULT_CA_CERTS_FILE
    body = open(p).read()
    print("boto", boto.__version__, "DEFAULT_CA_CERTS_FILE:", p)
    print("  certs:", body.count("BEGIN CERTIFICATE"))
    import ssl as _s
    ctx=_s.create_default_context(cafile=p)
    print("  run CA in boto2 store:", any("AOSCP Interception CA" in str(x.get("subject","")) for x in ctx.get_ca_certs()))
except Exception as e:
    print("boto probe error:", type(e).__name__, e)
print("OS extracted pem certs:", open("/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem").read().count("BEGIN CERTIFICATE"))
PY
