E=/apollo/env/SearchServicesLegosService
KT=$E/jdk-17/bin/keytool
echo "merged store entries: $($KT -list -keystore $E/var/aoscp-run-truststore.jks -storepass amazon 2>/dev/null | grep -c trustedCertEntry)"
echo -n "run CA in merged store: "; $KT -list -v -keystore $E/var/aoscp-run-truststore.jks -storepass amazon 2>/dev/null | grep -c 'AOSCP Interception CA'
echo -n "shipped store untouched (entries): "; $KT -list -keystore $E/certs/InternalAndExternalTrustStore.jks -storepass amazon 2>/dev/null | grep -c trustedCertEntry
echo "extracted OS pem certs: $(grep -c 'BEGIN CERTIFICATE' /etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem)"
python3 -c "import ssl;c=ssl.create_default_context();print('python default trust certs:',len(c.get_ca_certs()));print('run CA in python trust:',any('AOSCP Interception CA' in str(x.get('subject','')) for x in c.get_ca_certs()))"
python3 -V
