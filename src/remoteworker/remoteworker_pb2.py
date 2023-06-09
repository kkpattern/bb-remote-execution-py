# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: remoteworker/remoteworker.proto
"""Generated protocol buffer code."""
from google.protobuf.internal import builder as _builder
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import symbol_database as _symbol_database
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


from build.bazel.remote.execution.v2 import remote_execution_pb2 as build_dot_bazel_dot_remote_dot_execution_dot_v2_dot_remote__execution__pb2
from google.protobuf import any_pb2 as google_dot_protobuf_dot_any__pb2
from google.protobuf import empty_pb2 as google_dot_protobuf_dot_empty__pb2
from google.protobuf import timestamp_pb2 as google_dot_protobuf_dot_timestamp__pb2


DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x1fremoteworker/remoteworker.proto\x12\x16\x62uildbarn.remoteworker\x1a\x36\x62uild/bazel/remote/execution/v2/remote_execution.proto\x1a\x19google/protobuf/any.proto\x1a\x1bgoogle/protobuf/empty.proto\x1a\x1fgoogle/protobuf/timestamp.proto\"\xbe\x02\n\x12SynchronizeRequest\x12K\n\tworker_id\x18\x01 \x03(\x0b\x32\x38.buildbarn.remoteworker.SynchronizeRequest.WorkerIdEntry\x12\x1c\n\x14instance_name_prefix\x18\x02 \x01(\t\x12;\n\x08platform\x18\x03 \x01(\x0b\x32).build.bazel.remote.execution.v2.Platform\x12\x12\n\nsize_class\x18\x05 \x01(\r\x12;\n\rcurrent_state\x18\x04 \x01(\x0b\x32$.buildbarn.remoteworker.CurrentState\x1a/\n\rWorkerIdEntry\x12\x0b\n\x03key\x18\x01 \x01(\t\x12\r\n\x05value\x18\x02 \x01(\t:\x02\x38\x01\"\x8c\x04\n\x0c\x43urrentState\x12&\n\x04idle\x18\x01 \x01(\x0b\x32\x16.google.protobuf.EmptyH\x00\x12\x43\n\texecuting\x18\x02 \x01(\x0b\x32..buildbarn.remoteworker.CurrentState.ExecutingH\x00\x1a\xfe\x02\n\tExecuting\x12>\n\raction_digest\x18\x01 \x01(\x0b\x32\'.build.bazel.remote.execution.v2.Digest\x12)\n\x07started\x18\x02 \x01(\x0b\x32\x16.google.protobuf.EmptyH\x00\x12\x31\n\x0f\x66\x65tching_inputs\x18\x03 \x01(\x0b\x32\x16.google.protobuf.EmptyH\x00\x12)\n\x07running\x18\x04 \x01(\x0b\x32\x16.google.protobuf.EmptyH\x00\x12\x33\n\x11uploading_outputs\x18\x05 \x01(\x0b\x32\x16.google.protobuf.EmptyH\x00\x12\x45\n\tcompleted\x18\x06 \x01(\x0b\x32\x30.build.bazel.remote.execution.v2.ExecuteResponseH\x00\x12\x19\n\x11prefer_being_idle\x18\x07 \x01(\x08\x42\x11\n\x0f\x65xecution_stateB\x0e\n\x0cworker_state\"\x8f\x01\n\x13SynchronizeResponse\x12;\n\x17next_synchronization_at\x18\x01 \x01(\x0b\x32\x1a.google.protobuf.Timestamp\x12;\n\rdesired_state\x18\x02 \x01(\x0b\x32$.buildbarn.remoteworker.DesiredState\"\xbc\x04\n\x0c\x44\x65siredState\x12&\n\x04idle\x18\x01 \x01(\x0b\x32\x16.google.protobuf.EmptyH\x00\x12\x43\n\texecuting\x18\x02 \x01(\x0b\x32..buildbarn.remoteworker.DesiredState.ExecutingH\x00\x1a\xae\x03\n\tExecuting\x12>\n\raction_digest\x18\x01 \x01(\x0b\x32\'.build.bazel.remote.execution.v2.Digest\x12\x37\n\x06\x61\x63tion\x18\x02 \x01(\x0b\x32\'.build.bazel.remote.execution.v2.Action\x12\x34\n\x10queued_timestamp\x18\x04 \x01(\x0b\x32\x1a.google.protobuf.Timestamp\x12\x30\n\x12\x61uxiliary_metadata\x18\x06 \x03(\x0b\x32\x14.google.protobuf.Any\x12\x1c\n\x14instance_name_suffix\x18\x07 \x01(\t\x12^\n\x11w3c_trace_context\x18\x08 \x03(\x0b\x32\x43.buildbarn.remoteworker.DesiredState.Executing.W3cTraceContextEntry\x1a\x36\n\x14W3cTraceContextEntry\x12\x0b\n\x03key\x18\x01 \x01(\t\x12\r\n\x05value\x18\x02 \x01(\t:\x02\x38\x01J\x04\x08\x03\x10\x04J\x04\x08\x05\x10\x06\x42\x0e\n\x0cworker_state2x\n\x0eOperationQueue\x12\x66\n\x0bSynchronize\x12*.buildbarn.remoteworker.SynchronizeRequest\x1a+.buildbarn.remoteworker.SynchronizeResponseBAZ?github.com/buildbarn/bb-remote-execution/pkg/proto/remoteworkerb\x06proto3')

_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, globals())
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'remoteworker.remoteworker_pb2', globals())
if _descriptor._USE_C_DESCRIPTORS == False:

  DESCRIPTOR._options = None
  DESCRIPTOR._serialized_options = b'Z?github.com/buildbarn/bb-remote-execution/pkg/proto/remoteworker'
  _SYNCHRONIZEREQUEST_WORKERIDENTRY._options = None
  _SYNCHRONIZEREQUEST_WORKERIDENTRY._serialized_options = b'8\001'
  _DESIREDSTATE_EXECUTING_W3CTRACECONTEXTENTRY._options = None
  _DESIREDSTATE_EXECUTING_W3CTRACECONTEXTENTRY._serialized_options = b'8\001'
  _SYNCHRONIZEREQUEST._serialized_start=205
  _SYNCHRONIZEREQUEST._serialized_end=523
  _SYNCHRONIZEREQUEST_WORKERIDENTRY._serialized_start=476
  _SYNCHRONIZEREQUEST_WORKERIDENTRY._serialized_end=523
  _CURRENTSTATE._serialized_start=526
  _CURRENTSTATE._serialized_end=1050
  _CURRENTSTATE_EXECUTING._serialized_start=652
  _CURRENTSTATE_EXECUTING._serialized_end=1034
  _SYNCHRONIZERESPONSE._serialized_start=1053
  _SYNCHRONIZERESPONSE._serialized_end=1196
  _DESIREDSTATE._serialized_start=1199
  _DESIREDSTATE._serialized_end=1771
  _DESIREDSTATE_EXECUTING._serialized_start=1325
  _DESIREDSTATE_EXECUTING._serialized_end=1755
  _DESIREDSTATE_EXECUTING_W3CTRACECONTEXTENTRY._serialized_start=1689
  _DESIREDSTATE_EXECUTING_W3CTRACECONTEXTENTRY._serialized_end=1743
  _OPERATIONQUEUE._serialized_start=1773
  _OPERATIONQUEUE._serialized_end=1893
# @@protoc_insertion_point(module_scope)
