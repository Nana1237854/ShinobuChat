export async function captureScreen(): Promise<void> {
  if (!navigator.mediaDevices?.getDisplayMedia) {
    throw new Error('Screen Capture API is not available in this browser');
  }

  const stream = await navigator.mediaDevices.getDisplayMedia({ video: true, audio: false });
  const [track] = stream.getVideoTracks();
  const video = document.createElement('video');
  video.srcObject = stream;
  video.muted = true;
  await video.play();
  await new Promise(resolve => window.setTimeout(resolve, 120));
  const canvas = document.createElement('canvas');
  canvas.width = video.videoWidth || 1280;
  canvas.height = video.videoHeight || 720;
  canvas.getContext('2d')?.drawImage(video, 0, 0, canvas.width, canvas.height);
  track.stop();
  const link = document.createElement('a');
  link.href = canvas.toDataURL('image/png');
  link.download = `shinobu-screenshot-${Date.now()}.png`;
  link.click();
}
