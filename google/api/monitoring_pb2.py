# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: google/api/monitoring.proto
"""Generated protocol buffer code."""
from google.protobuf.internal import builder as _builder
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import symbol_database as _symbol_database
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()




DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x1bgoogle/api/monitoring.proto\x12\ngoogle.api\"\xec\x01\n\nMonitoring\x12K\n\x15producer_destinations\x18\x01 \x03(\x0b\x32,.google.api.Monitoring.MonitoringDestination\x12K\n\x15\x63onsumer_destinations\x18\x02 \x03(\x0b\x32,.google.api.Monitoring.MonitoringDestination\x1a\x44\n\x15MonitoringDestination\x12\x1a\n\x12monitored_resource\x18\x01 \x01(\t\x12\x0f\n\x07metrics\x18\x02 \x03(\tBq\n\x0e\x63om.google.apiB\x0fMonitoringProtoP\x01ZEgoogle.golang.org/genproto/googleapis/api/serviceconfig;serviceconfig\xa2\x02\x04GAPIb\x06proto3')

_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, globals())
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'google.api.monitoring_pb2', globals())
if _descriptor._USE_C_DESCRIPTORS == False:

  DESCRIPTOR._options = None
  DESCRIPTOR._serialized_options = b'\n\016com.google.apiB\017MonitoringProtoP\001ZEgoogle.golang.org/genproto/googleapis/api/serviceconfig;serviceconfig\242\002\004GAPI'
  _MONITORING._serialized_start=44
  _MONITORING._serialized_end=280
  _MONITORING_MONITORINGDESTINATION._serialized_start=212
  _MONITORING_MONITORINGDESTINATION._serialized_end=280
# @@protoc_insertion_point(module_scope)
