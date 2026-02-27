/**
 * AudioWorklet processor for capturing PCM audio from the microphone.
 * Converts Float32 samples to 16-bit PCM Int16 and posts via port.
 */
class PcmCaptureProcessor extends AudioWorkletProcessor {
    process(inputs) {
        const input = inputs[0]
        if (input && input.length > 0) {
            const float32 = input[0]
            const int16 = new Int16Array(float32.length)
            for (let i = 0; i < float32.length; i++) {
                const s = Math.max(-1, Math.min(1, float32[i]))
                int16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF
            }
            this.port.postMessage(int16.buffer, [int16.buffer])
        }
        return true
    }
}

registerProcessor('pcm-capture', PcmCaptureProcessor)
