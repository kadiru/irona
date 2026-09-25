package dev.irona.player;

import android.app.Activity;
import android.graphics.Color;
import android.media.AudioAttributes;
import android.media.AudioManager;
import android.media.MediaPlayer;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.view.Gravity;
import android.view.WindowManager;
import android.widget.ImageButton;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONObject;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.UUID;
import java.util.concurrent.Callable;
import java.util.concurrent.FutureTask;
import java.util.concurrent.TimeUnit;
import fi.iki.elonen.NanoHTTPD;

public final class MainActivity extends Activity {
    private static final long LEASE_MS = 3500;
    private final Object lock = new Object();
    private final Handler main = new Handler(Looper.getMainLooper());
    private final String sessionId = UUID.randomUUID().toString().replace("-", "");
    private Receiver server;
    private MediaPlayer player;
    private AudioManager audio;
    private String token;
    private Job job;
    private TextView status;
    private TextView detail;
    private ImageButton stop;
    private boolean visible;

    private static final class Job {
        final String id;
        final File file;
        String state = "preparing";
        String error = "";
        boolean started;
        long heartbeat = SystemClock.elapsedRealtime();
        Job(String id, File file) { this.id = id; this.file = file; }
    }

    private final AudioManager.OnAudioFocusChangeListener focus = change -> {
        if (change < 0) main.post(() -> finish("error", "audio_focus"));
    };

    private final Runnable watchdog = new Runnable() {
        @Override public void run() {
            synchronized (lock) {
                if (active() && SystemClock.elapsedRealtime() - job.heartbeat > LEASE_MS) {
                    finish("error", "lease_expired");
                }
            }
            if (visible) main.postDelayed(this, 200);
        }
    };

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        audio = (AudioManager) getSystemService(AUDIO_SERVICE);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        layout.setGravity(Gravity.CENTER_VERTICAL);
        int pad = (int) (40 * getResources().getDisplayMetrics().density);
        layout.setPadding(pad, pad, pad, pad);
        layout.setBackgroundColor(Color.rgb(245, 247, 246));
        TextView title = new TextView(this);
        title.setText(R.string.irona); title.setTextSize(30); title.setTextColor(Color.rgb(32, 40, 37));
        title.setCompoundDrawablesWithIntrinsicBounds(R.drawable.irona_icon, 0, 0, 0);
        title.setCompoundDrawablePadding(16);
        layout.addView(title);
        TextView destination = new TextView(this);
        destination.setText(R.string.destination); destination.setTextSize(16);
        layout.addView(destination);
        status = new TextView(this);
        status.setTextSize(26); status.setPadding(0, pad, 0, 12);
        layout.addView(status);
        detail = new TextView(this); detail.setTextSize(14);
        layout.addView(detail);
        stop = new ImageButton(this);
        stop.setImageResource(R.drawable.stop_icon);
        stop.setContentDescription(getString(R.string.stop_audio));
        stop.setBackgroundResource(android.R.drawable.list_selector_background);
        stop.setOnClickListener(v -> finish("stopped", ""));
        int buttonSize = (int) (56 * getResources().getDisplayMetrics().density);
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(buttonSize, buttonSize);
        params.topMargin = pad;
        layout.addView(stop, params);
        setContentView(layout);
        File[] stale = getCacheDir().listFiles((dir, name) -> name.startsWith("irona-") && name.endsWith(".audio"));
        if (stale != null) for (File file : stale) file.delete();
        try (FileInputStream input = new FileInputStream(new File(getFilesDir(), "irona-token"))) {
            byte[] bytes = new byte[129];
            int count = input.read(bytes);
            token = new String(bytes, 0, Math.max(0, count), StandardCharsets.US_ASCII).trim();
            if (!token.matches("[A-Za-z0-9_-]{32,128}")) throw new IOException();
        } catch (IOException error) {
            token = null;
        }
        render();
    }

    @Override protected void onStart() {
        super.onStart();
        visible = true;
        if (token != null) {
            try {
                server = new Receiver();
                server.start(1500, true);
                main.post(watchdog);
            } catch (IOException error) {
                status.setText(R.string.connection_unavailable);
                detail.setText(R.string.port_busy);
            }
        }
    }

    @Override protected void onStop() {
        visible = false;
        main.removeCallbacks(watchdog);
        finish("stopped", "");
        if (server != null) { server.stop(); server = null; }
        super.onStop();
    }

    private boolean active() {
        return job != null && (job.state.equals("preparing") || job.state.equals("playing"));
    }

    private void render() {
        synchronized (lock) {
            if (token == null) {
                status.setText(R.string.pairing_required); detail.setText(R.string.token_missing);
            } else if (job == null) {
                status.setText(R.string.ready); detail.setText(R.string.idle);
            } else {
                int text = job.state.equals("playing") ? R.string.speaking : job.state.equals("preparing") ? R.string.preparing : job.state.equals("error") ? R.string.playback_error : R.string.ready;
                status.setText(text);
                detail.setText(job.error.isEmpty() ? job.state : job.error.replace('_', ' '));
            }
            stop.setEnabled(active());
        }
    }

    private void finish(String state, String error) {
        synchronized (lock) {
            if (!active()) return;
            if (player != null) {
                try { player.stop(); } catch (IllegalStateException ignored) { }
                player.release(); player = null;
            }
            audio.abandonAudioFocus(focus);
            job.state = state; job.error = error;
            job.file.delete();
            render();
        }
    }

    private JSONObject snapshot() {
        synchronized (lock) {
            JSONObject data = new JSONObject();
            try {
                data.put("protocol", "irona-temi/1"); data.put("session", sessionId);
                data.put("id", job == null ? "" : job.id);
                data.put("state", job == null ? "idle" : job.state);
                data.put("started", job != null && job.started);
                data.put("error", job == null ? "" : job.error);
            } catch (org.json.JSONException impossible) { throw new IllegalStateException(impossible); }
            return data;
        }
    }

    private boolean begin(String id, File file, float volume) {
        synchronized (lock) {
            if (!visible || active() || (job != null && job.id.equals(id))) return false;
            job = new Job(id, file);
            if (audio.requestAudioFocus(focus, AudioManager.STREAM_MUSIC, AudioManager.AUDIOFOCUS_GAIN_TRANSIENT) != AudioManager.AUDIOFOCUS_REQUEST_GRANTED) {
                finish("error", "audio_focus"); return true;
            }
            try {
                final MediaPlayer next = new MediaPlayer();
                player = next;
                next.setAudioAttributes(new AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_MEDIA).setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).build());
                next.setVolume(volume, volume);
                next.setDataSource(file.getAbsolutePath());
                next.setOnPreparedListener(ready -> {
                    synchronized (lock) {
                        if (player != ready || !active()) return;
                        if (SystemClock.elapsedRealtime() - job.heartbeat > LEASE_MS) { finish("error", "lease_expired"); return; }
                        try {
                            ready.start(); job.started = true; job.state = "playing"; render();
                        } catch (IllegalStateException error) { finish("error", "decode"); }
                    }
                });
                next.setOnCompletionListener(done -> { if (player == done) finish("completed", ""); });
                next.setOnErrorListener((failed, what, extra) -> { if (player == failed) finish("error", "decode"); return true; });
                next.prepareAsync();
                render();
            } catch (IOException | IllegalStateException error) { finish("error", "decode"); }
            return true;
        }
    }

    private final class Receiver extends NanoHTTPD {
        Receiver() { super("127.0.0.1", 8766); }

        private Response reply(Response.Status code, JSONObject body) {
            Response response = newFixedLengthResponse(code, "application/json", body.toString());
            response.addHeader("Cache-Control", "no-store");
            response.closeConnection(true);
            return response;
        }

        private Response error(Response.Status code) { return reply(code, new JSONObject()); }

        private Response onMain(Callable<Response> call) {
            FutureTask<Response> task = new FutureTask<>(call);
            main.post(task);
            try { return task.get(2, TimeUnit.SECONDS); }
            catch (Exception unavailable) { task.cancel(false); return error(Response.Status.SERVICE_UNAVAILABLE); }
        }

        @Override public Response serve(IHTTPSession request) {
            String auth = request.getHeaders().get("authorization");
            if (auth == null || !MessageDigest.isEqual(auth.getBytes(StandardCharsets.UTF_8), ("Bearer " + token).getBytes(StandardCharsets.UTF_8))) {
                return error(Response.Status.UNAUTHORIZED);
            }
            String uri = request.getUri();
            if (request.getMethod() == Method.GET && uri.equals("/health")) return reply(Response.Status.OK, snapshot());
            String[] path = uri.split("/");
            if (path.length != 3 || !path[2].matches("[a-f0-9]{32}")) return error(Response.Status.NOT_FOUND);
            String id = path[2];
            if (request.getMethod() == Method.GET && path[1].equals("status")) {
                return onMain(() -> {
                    synchronized (lock) {
                        if (job == null || !job.id.equals(id)) return error(Response.Status.NOT_FOUND);
                        if (active() && SystemClock.elapsedRealtime() - job.heartbeat > LEASE_MS) finish("error", "lease_expired");
                        job.heartbeat = SystemClock.elapsedRealtime();
                        return reply(Response.Status.OK, snapshot());
                    }
                });
            }
            if (request.getMethod() == Method.POST && path[1].equals("stop")) {
                return onMain(() -> {
                    synchronized (lock) {
                        if (job == null || !job.id.equals(id)) return error(Response.Status.NOT_FOUND);
                        finish("stopped", "");
                        return reply(Response.Status.OK, snapshot());
                    }
                });
            }
            if (request.getMethod() != Method.POST || !path[1].equals("play")) return error(Response.Status.NOT_FOUND);
            synchronized (lock) {
                if (active() || (job != null && job.id.equals(id))) return error(Response.Status.CONFLICT);
            }
            File file = null;
            try {
                String size = request.getHeaders().get("content-length");
                String level = request.getParms().get("volume");
                int length = Integer.parseInt(size == null ? "0" : size);
                float volume = Float.parseFloat(level == null ? "0.6" : level);
                if (length < 1 || length > 8_000_000 || Float.isNaN(volume) || volume < 0.01f || volume > 1f) return error(Response.Status.BAD_REQUEST);
                if (request.getHeaders().containsKey("transfer-encoding")) return error(Response.Status.BAD_REQUEST);
                file = File.createTempFile("irona-", ".audio", getCacheDir());
                try (FileOutputStream output = new FileOutputStream(file)) {
                    byte[] buffer = new byte[8192];
                    int left = length;
                    long deadline = SystemClock.elapsedRealtime() + 5000;
                    while (left > 0) {
                        if (SystemClock.elapsedRealtime() > deadline) throw new IOException();
                        int count = request.getInputStream().read(buffer, 0, Math.min(left, buffer.length));
                        if (count < 1) throw new IOException();
                        output.write(buffer, 0, count); left -= count;
                    }
                }
                final File received = file;
                return onMain(() -> begin(id, received, volume) ? reply(Response.Status.OK, snapshot()) : error(Response.Status.CONFLICT));
            } catch (IOException | NumberFormatException badUpload) {
                return error(Response.Status.BAD_REQUEST);
            } finally {
                synchronized (lock) {
                    if (file != null && (job == null || job.file != file)) file.delete();
                }
            }
        }
    }
}
