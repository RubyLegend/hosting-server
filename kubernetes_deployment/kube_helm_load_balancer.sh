#!/bin/bash -x
helm upgrade --install ingress-nginx ingress-nginx/ingress-nginx \
  --namespace default \
  --set controller.service.loadBalancerIP=172.166.225.54 \
  --set controller.service.annotations."service\.beta\.kubernetes\.io/azure-load-balancer-health-probe-request-path"=/healthz \
  --set controller.service.ports.http=65533 \
  --set controller.service.targetPorts.http=80 \
  --set controller.service.enableHttps=false \
  --set data.strict-validate-path-type=false
