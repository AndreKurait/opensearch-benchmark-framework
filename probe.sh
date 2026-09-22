set -eu
E=/apollo/env/SearchServicesLegosService
KT=$E/jdk-17/bin/keytool
echo "== shipped store entries: $($KT -list -keystore $E/certs/InternalAndExternalTrustStore.jks -storepass amazon 2>/dev/null | grep -c trustedCertEntry)"
cp $E/certs/InternalAndExternalTrustStore.jks /tmp/naive.jks
set +e
$KT -importcert -noprompt -trustcacerts -alias naive-bundle -file /ca/run-ca-bundle.pem \
    -keystore /tmp/naive.jks -storepass amazon >/tmp/kt.out 2>&1
echo "== naive keytool -importcert exit: $?"
set -e
echo "== entries after naive import: $($KT -list -keystore /tmp/naive.jks -storepass amazon 2>/dev/null | grep -c trustedCertEntry)"
echo "== what it actually imported:"
$KT -list -v -alias naive-bundle -keystore /tmp/naive.jks -storepass amazon 2>/dev/null | grep -m1 '^Owner:'
echo "== is the run CA in the naive store?"
$KT -list -keystore /tmp/naive.jks -storepass amazon -rfc 2>/dev/null | grep -c 'AOSCP' || true
$KT -list -v -keystore /tmp/naive.jks -storepass amazon 2>/dev/null | grep -c 'AOSCP Interception CA' || echo "0 (ABSENT)"
