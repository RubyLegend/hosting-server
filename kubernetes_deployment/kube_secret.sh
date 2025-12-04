#!/bin/bash
kubectl create secret generic azure-secret \
  --from-literal=azurestorageaccountname=videosg \
  --from-literal=azurestorageaccountkey=<SHARE_KEY>
