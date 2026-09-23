"""WASAPI speaker loopback delivered through PortAudio's callback thread."""
import queue,time
import numpy as np
import pyaudiowpatch as pa

class CallbackLoopback:
    def __init__(self):
        self.client=pa.PyAudio();self.stream=None;self.silence_stream=None;self.events=[];self.failure=None
        self.packets=queue.Queue(maxsize=200);self.pending=b''
        self.device=self.client.get_default_wasapi_loopback()
        if not self.device.get('isLoopbackDevice'):
            self.client.terminate();raise RuntimeError('Refusing a microphone device')
        if self.device['maxInputChannels']<2:
            self.client.terminate();raise RuntimeError('Stereo speaker loopback is unavailable')
        self.device_name=self.device['name']
    def __enter__(self):
        def callback(data,frames,timing,status):
            if status:self.events.append({'at':time.time(),'message':'audio discontinuity: PortAudio callback flags '+str(status)})
            try:self.packets.put_nowait(data)
            except queue.Full:
                self.failure='Audio callback queue overflow';return (None,pa.paAbort)
            return (None,pa.paContinue)
        try:
            # WASAPI may stop supplying packets when every render session is
            # silent. Keep the same speaker endpoint clocked with digital zero;
            # the capture still receives the real system mix, never a microphone.
            host=self.client.get_host_api_info_by_type(pa.paWASAPI)
            output=self.client.get_device_info_by_index(host['defaultOutputDevice'])
            if output['name'] not in self.device_name:
                raise RuntimeError('Loopback and silent render endpoints differ')
            def silence(data,frames,timing,status):
                return (b'\x00'*(frames*4),pa.paContinue)
            self.silence_stream=self.client.open(format=pa.paInt16,channels=2,rate=48000,output=True,
                output_device_index=output['index'],frames_per_buffer=480,stream_callback=silence)
            self.stream=self.client.open(format=pa.paInt16,channels=2,rate=48000,input=True,
                input_device_index=self.device['index'],frames_per_buffer=480,stream_callback=callback)
        except BaseException:
            if self.silence_stream:self.silence_stream.stop_stream();self.silence_stream.close()
            self.client.terminate();raise
        return self
    def record(self,numframes):
        size=numframes*4
        while len(self.pending)<size:
            if self.failure:raise RuntimeError(self.failure)
            try:self.pending+=self.packets.get(timeout=2)
            except queue.Empty:raise RuntimeError('WASAPI callback stopped producing audio') from None
        data,self.pending=self.pending[:size],self.pending[size:]
        return np.frombuffer(data,dtype='<i2').reshape(-1,2).astype(np.float32)/32768
    def take_events(self):
        result,self.events=self.events,[]
        return result
    def __exit__(self,*args):
        try:
            if self.stream:self.stream.stop_stream();self.stream.close()
        finally:
            try:
                if self.silence_stream:self.silence_stream.stop_stream();self.silence_stream.close()
            finally:self.client.terminate()
