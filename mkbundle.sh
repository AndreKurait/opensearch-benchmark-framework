set -eu
openssl req -x509 -newkey rsa:2048 -nodes -keyout /tmp/ca.key -out /tmp/ca.pem -days 2 \
  -subj "/C=US/O=AOSCPLocalStack/CN=AOSCP Interception CA" -addext "basicConstraints=critical,CA:TRUE" >/dev/null 2>&1
cat /etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem /tmp/ca.pem > /tmp/bundle.pem
echo "bundle certs: $(grep -c 'BEGIN CERTIFICATE' /tmp/bundle.pem)"
echo "shipped store entries: $(/apollo/env/SearchServicesLegosService/jdk-17/bin/keytool -list -keystore /apollo/env/SearchServicesLegosService/certs/InternalAndExternalTrustStore.jks -storepass amazon 2>/dev/null | grep -c 'trustedCertEntry')"
cp /tmp/bundle.pem /work/bundle.pem
