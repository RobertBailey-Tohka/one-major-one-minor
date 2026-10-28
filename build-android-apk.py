#!/usr/bin/env python3
"""
Builds the standalone Android APK (with Interactive Home Screen Widget: Daily / Weekly / Tasks)
for "1 Minor + 1 Major" using the standard Android SDK build-tools (aapt2, javac, d8, zipalign, apksigner).
"""
import os
import sys
import glob
import shutil
import struct
import zlib
import subprocess

PACKAGE_NAME = "com.robertbailey.oneminoronemajor"
PACKAGE_PATH = PACKAGE_NAME.replace(".", "/")
BUILD_DIR = os.path.abspath("build_apk_work")
OUT_APK = os.path.abspath("one-minor-one-major.apk")


def find_sdk_tools():
    sdk_root = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")
    if not sdk_root or not os.path.isdir(sdk_root):
        for candidate in ["/usr/local/lib/android/sdk", os.path.expanduser("~/Android/Sdk")]:
            if os.path.isdir(candidate):
                sdk_root = candidate
                break
    if not sdk_root:
        raise RuntimeError("ANDROID_HOME not found")

    bt_dirs = sorted(glob.glob(os.path.join(sdk_root, "build-tools", "*")))
    if not bt_dirs:
        raise RuntimeError("No Android build-tools found in " + sdk_root)
    bt_dir = bt_dirs[-1]

    plat_jars = sorted(glob.glob(os.path.join(sdk_root, "platforms", "android-*", "android.jar")))
    if not plat_jars:
        raise RuntimeError("No Android platform android.jar found in " + sdk_root)
    android_jar = plat_jars[-1]

    return {
        "aapt2": os.path.join(bt_dir, "aapt2"),
        "d8": os.path.join(bt_dir, "d8"),
        "zipalign": os.path.join(bt_dir, "zipalign"),
        "apksigner": os.path.join(bt_dir, "apksigner"),
        "android_jar": android_jar,
    }


def make_png_icon(filepath, size=192):
    """Generates a clean emerald-and-blue app icon PNG with a checkmark."""
    width = height = size
    raw_rows = []
    for y in range(height):
        row = bytearray([0])
        for x in range(width):
            # Rounded square mask
            margin = size * 0.06
            radius = size * 0.22
            dx = max(margin + radius - x, 0, x - (size - 1 - margin - radius))
            dy = max(margin + radius - y, 0, y - (size - 1 - margin - radius))
            if dx * dx + dy * dy > radius * radius:
                row.extend((0, 0, 0, 0))
                continue

            # Two-tone diagonal gradient (Minor Emerald -> Major Blue)
            t = (x + y) / float(2 * size)
            r = int(16 * (1 - t) + 29 * t)
            g = int(185 * (1 - t) + 78 * t)
            b = int(129 * (1 - t) + 216 * t)

            # White checkmark in the center
            nx = x / float(size)
            ny = y / float(size)
            # Segment 1: (0.28, 0.52) -> (0.44, 0.68)
            # Segment 2: (0.44, 0.68) -> (0.74, 0.34)
            in_check = False
            if 0.25 <= nx <= 0.45:
                expected_y = 0.52 + (nx - 0.28) * 1.0
                if abs(ny - expected_y) < 0.065:
                    in_check = True
            if 0.42 <= nx <= 0.76:
                expected_y = 0.68 - (nx - 0.44) * 1.13
                if abs(ny - expected_y) < 0.065:
                    in_check = True

            if in_check:
                row.extend((255, 255, 255, 255))
            else:
                row.extend((r, g, b, 255))
        raw_rows.append(bytes(row))

    raw_data = b"".join(raw_rows)

    def chunk(ch_type, data):
        crc = zlib.crc32(ch_type + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + ch_type + data + struct.pack(">I", crc)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    png_bytes = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(raw_data, 9))
        + chunk(b"IEND", b"")
    )
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "wb") as f:
        f.write(png_bytes)


def write_text(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content.lstrip())


def generate_project_files():
    if os.path.exists(BUILD_DIR):
        shutil.rmtree(BUILD_DIR)
    os.makedirs(BUILD_DIR, exist_ok=True)

    res_dir = os.path.join(BUILD_DIR, "res")
    src_dir = os.path.join(BUILD_DIR, "src", PACKAGE_PATH)
    assets_dir = os.path.join(BUILD_DIR, "assets")
    os.makedirs(src_dir, exist_ok=True)
    os.makedirs(assets_dir, exist_ok=True)

    # Copy index.html into assets so offline fallback is always bundled
    shutil.copyfile("index.html", os.path.join(assets_dir, "index.html"))

    # Create PNG launcher icon
    make_png_icon(os.path.join(res_dir, "drawable", "ic_launcher.png"), 192)

    # 1. AndroidManifest.xml
    write_text(
        os.path.join(BUILD_DIR, "AndroidManifest.xml"),
        f"""<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    package="{PACKAGE_NAME}"
    android:versionCode="4"
    android:versionName="4.0">

    <uses-sdk android:minSdkVersion="26" android:targetSdkVersion="33" />
    <uses-permission android:name="android.permission.INTERNET" />
    <uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />

    <application
        android:label="1 Minor + 1 Major"
        android:icon="@drawable/ic_launcher"
        android:usesCleartextTraffic="true"
        android:theme="@android:style/Theme.DeviceDefault.Light.NoActionBar">

        <activity
            android:name=".MainActivity"
            android:exported="true"
            android:launchMode="singleTask"
            android:configChanges="orientation|screenSize|keyboardHidden">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>

        <receiver
            android:name=".PlannerWidgetProvider"
            android:label="1 Minor + 1 Major"
            android:exported="true">
            <intent-filter>
                <action android:name="android.appwidget.action.APPWIDGET_UPDATE" />
                <action android:name="{PACKAGE_NAME}.ACTION_SWITCH_TAB" />
                <action android:name="{PACKAGE_NAME}.ACTION_ROW_CLICK" />
                <action android:name="{PACKAGE_NAME}.ACTION_REFRESH_WIDGET" />
            </intent-filter>
            <meta-data
                android:name="android.appwidget.provider"
                android:resource="@xml/planner_widget_info" />
        </receiver>

        <service
            android:name=".PlannerWidgetService"
            android:permission="android.permission.BIND_REMOTEVIEWS"
            android:exported="false" />
    </application>
</manifest>
""",
    )

    # 2. Widget Provider XML Metadata
    write_text(
        os.path.join(res_dir, "xml", "planner_widget_info.xml"),
        """<?xml version="1.0" encoding="utf-8"?>
<appwidget-provider xmlns:android="http://schemas.android.com/apk/res/android"
    android:minWidth="250dp"
    android:minHeight="180dp"
    android:targetCellWidth="4"
    android:targetCellHeight="3"
    android:minResizeWidth="180dp"
    android:minResizeHeight="110dp"
    android:updatePeriodMillis="1800000"
    android:initialLayout="@layout/widget_planner"
    android:resizeMode="horizontal|vertical"
    android:widgetCategory="home_screen" />
""",
    )

    # 3. Drawable backgrounds for the Widget
    write_text(
        os.path.join(res_dir, "drawable", "bg_widget_card.xml"),
        """<?xml version="1.0" encoding="utf-8"?>
<shape xmlns:android="http://schemas.android.com/apk/res/android" android:shape="rectangle">
    <solid android:color="#FFFFFF" />
    <corners android:radius="18dp" />
    <stroke android:width="1dp" android:color="#CBD5E1" />
</shape>
""",
    )

    write_text(
        os.path.join(res_dir, "drawable", "bg_tab_active.xml"),
        """<?xml version="1.0" encoding="utf-8"?>
<shape xmlns:android="http://schemas.android.com/apk/res/android" android:shape="rectangle">
    <solid android:color="#1D4ED8" />
    <corners android:radius="10dp" />
</shape>
""",
    )

    write_text(
        os.path.join(res_dir, "drawable", "bg_tab_inactive.xml"),
        """<?xml version="1.0" encoding="utf-8"?>
<shape xmlns:android="http://schemas.android.com/apk/res/android" android:shape="rectangle">
    <solid android:color="#F1F5F9" />
    <corners android:radius="10dp" />
</shape>
""",
    )

    write_text(
        os.path.join(res_dir, "drawable", "bg_row_card.xml"),
        """<?xml version="1.0" encoding="utf-8"?>
<shape xmlns:android="http://schemas.android.com/apk/res/android" android:shape="rectangle">
    <solid android:color="#F8FAFC" />
    <corners android:radius="10dp" />
    <stroke android:width="1dp" android:color="#E2E8F0" />
</shape>
""",
    )

    write_text(
        os.path.join(res_dir, "drawable", "bg_check_unchecked.xml"),
        """<?xml version="1.0" encoding="utf-8"?>
<shape xmlns:android="http://schemas.android.com/apk/res/android" android:shape="oval">
    <solid android:color="#FFFFFF" />
    <stroke android:width="2dp" android:color="#64748B" />
    <size android:width="26dp" android:height="26dp" />
</shape>
""",
    )

    write_text(
        os.path.join(res_dir, "drawable", "bg_check_checked.xml"),
        """<?xml version="1.0" encoding="utf-8"?>
<shape xmlns:android="http://schemas.android.com/apk/res/android" android:shape="oval">
    <solid android:color="#10B981" />
    <size android:width="26dp" android:height="26dp" />
</shape>
""",
    )

    # 4. Main Widget Layout (Header + 3 View Tabs + Scrollable ListView)
    write_text(
        os.path.join(res_dir, "layout", "widget_planner.xml"),
        """<?xml version="1.0" encoding="utf-8"?>
<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android"
    android:id="@+id/widget_root"
    android:layout_width="match_parent"
    android:layout_height="match_parent"
    android:orientation="vertical"
    android:background="@drawable/bg_widget_card"
    android:padding="12dp">

    <!-- Top Header Row: Date Title + Sync & Add Buttons -->
    <LinearLayout
        android:layout_width="match_parent"
        android:layout_height="wrap_content"
        android:orientation="horizontal"
        android:gravity="center_vertical"
        android:paddingBottom="8dp">

        <TextView
            android:id="@+id/widget_date_title"
            android:layout_width="0dp"
            android:layout_height="wrap_content"
            android:layout_weight="1"
            android:text="1 Minor + 1 Major"
            android:textColor="#0F172A"
            android:textSize="15sp"
            android:textStyle="bold"
            android:singleLine="true"
            android:ellipsize="end" />

        <TextView
            android:id="@+id/widget_btn_refresh"
            android:layout_width="32dp"
            android:layout_height="30dp"
            android:gravity="center"
            android:text="↻"
            android:textColor="#334155"
            android:textSize="16sp"
            android:textStyle="bold"
            android:background="@drawable/bg_tab_inactive"
            android:layout_marginEnd="6dp" />

        <TextView
            android:id="@+id/widget_btn_add"
            android:layout_width="32dp"
            android:layout_height="30dp"
            android:gravity="center"
            android:text="＋"
            android:textColor="#FFFFFF"
            android:textSize="15sp"
            android:textStyle="bold"
            android:background="@drawable/bg_tab_active" />
    </LinearLayout>

    <!-- 3 View Switcher Tabs: Daily | Weekly | Tasks -->
    <LinearLayout
        android:layout_width="match_parent"
        android:layout_height="wrap_content"
        android:orientation="horizontal"
        android:paddingBottom="8dp">

        <TextView
            android:id="@+id/widget_tab_daily"
            android:layout_width="0dp"
            android:layout_height="30dp"
            android:layout_weight="1"
            android:gravity="center"
            android:text="☀️ Daily"
            android:textSize="12sp"
            android:textStyle="bold"
            android:textColor="#FFFFFF"
            android:background="@drawable/bg_tab_active"
            android:layout_marginEnd="4dp" />

        <TextView
            android:id="@+id/widget_tab_weekly"
            android:layout_width="0dp"
            android:layout_height="30dp"
            android:layout_weight="1"
            android:gravity="center"
            android:text="🗓️ Weekly"
            android:textSize="12sp"
            android:textStyle="bold"
            android:textColor="#475569"
            android:background="@drawable/bg_tab_inactive"
            android:layout_marginEnd="4dp" />

        <TextView
            android:id="@+id/widget_tab_tasks"
            android:layout_width="0dp"
            android:layout_height="30dp"
            android:layout_weight="1"
            android:gravity="center"
            android:text="☑️ Tasks"
            android:textSize="12sp"
            android:textStyle="bold"
            android:textColor="#475569"
            android:background="@drawable/bg_tab_inactive" />
    </LinearLayout>

    <!-- Scrollable List of Habits / Slots / Tasks -->
    <ListView
        android:id="@+id/widget_list_view"
        android:layout_width="match_parent"
        android:layout_height="0dp"
        android:layout_weight="1"
        android:divider="@android:color/transparent"
        android:dividerHeight="5dp" />

    <TextView
        android:id="@+id/widget_empty_view"
        android:layout_width="match_parent"
        android:layout_height="0dp"
        android:layout_weight="1"
        android:gravity="center"
        android:text="Tap to open 1 Minor + 1 Major &amp; sync your tasks"
        android:textColor="#64748B"
        android:textSize="13sp"
        android:visibility="gone" />
</LinearLayout>
""",
    )

    # 5. Widget List Item Layouts (Section Header Row & Checkable Task/Habit Row)
    write_text(
        os.path.join(res_dir, "layout", "widget_row_header.xml"),
        """<?xml version="1.0" encoding="utf-8"?>
<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android"
    android:id="@+id/row_header_root"
    android:layout_width="match_parent"
    android:layout_height="wrap_content"
    android:orientation="horizontal"
    android:paddingTop="6dp"
    android:paddingBottom="2dp"
    android:paddingStart="4dp"
    android:paddingEnd="4dp">

    <TextView
        android:id="@+id/row_header_text"
        android:layout_width="match_parent"
        android:layout_height="wrap_content"
        android:text="SECTION"
        android:textSize="11sp"
        android:textStyle="bold"
        android:textColor="#1D4ED8" />
</LinearLayout>
""",
    )

    write_text(
        os.path.join(res_dir, "layout", "widget_row_item.xml"),
        """<?xml version="1.0" encoding="utf-8"?>
<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android"
    android:id="@+id/row_item_root"
    android:layout_width="match_parent"
    android:layout_height="wrap_content"
    android:orientation="horizontal"
    android:gravity="center_vertical"
    android:background="@drawable/bg_row_card"
    android:padding="9dp">

    <!-- Direct Check-off Target on Wallpaper (Does NOT open app!) -->
    <FrameLayout
        android:id="@+id/row_check_TouchArea"
        android:layout_width="34dp"
        android:layout_height="34dp"
        android:layout_marginEnd="8dp">

        <TextView
            android:id="@+id/row_check_box"
            android:layout_width="26dp"
            android:layout_height="26dp"
            android:layout_gravity="center"
            android:gravity="center"
            android:text=""
            android:textColor="#FFFFFF"
            android:textSize="14sp"
            android:textStyle="bold"
            android:background="@drawable/bg_check_unchecked" />
    </FrameLayout>

    <!-- Task Title & Subtitle (Tapping opens app to view/edit) -->
    <LinearLayout
        android:id="@+id/row_text_area"
        android:layout_width="0dp"
        android:layout_height="wrap_content"
        android:layout_weight="1"
        android:orientation="vertical">

        <TextView
            android:id="@+id/row_item_title"
            android:layout_width="match_parent"
            android:layout_height="wrap_content"
            android:text="Task Title"
            android:textColor="#0F172A"
            android:textSize="13.5sp"
            android:textStyle="bold"
            android:maxLines="2"
            android:ellipsize="end" />

        <TextView
            android:id="@+id/row_item_subtitle"
            android:layout_width="match_parent"
            android:layout_height="wrap_content"
            android:text="Subtitle"
            android:textColor="#64748B"
            android:textSize="11sp"
            android:singleLine="true"
            android:ellipsize="end"
            android:paddingTop="2dp" />
    </LinearLayout>
</LinearLayout>
""",
    )

    # 6. Java Source: VaultCrypto.java (Exact match to index.html's SHA-256 stream cipher + Firebase sync)
    write_text(
        os.path.join(src_dir, "VaultCrypto.java"),
        f"""package {PACKAGE_NAME};

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.SecureRandom;
import org.json.JSONObject;

public class VaultCrypto {{

    public static byte[] sha256Bytes(byte[] input) throws Exception {{
        MessageDigest md = MessageDigest.getInstance("SHA-256");
        return md.digest(input);
    }}

    public static String bytesToHex(byte[] bytes) {{
        StringBuilder sb = new StringBuilder(bytes.length * 2);
        for (byte b : bytes) {{
            sb.append(String.format("%02x", b & 0xff));
        }}
        return sb.toString();
    }}

    public static byte[] hexToBytes(String hex) {{
        int len = hex.length() / 2;
        byte[] out = new byte[len];
        for (int i = 0; i < len; i++) {{
            out[i] = (byte) Integer.parseInt(hex.substring(i * 2, i * 2 + 2), 16);
        }}
        return out;
    }}

    public static JSONObject decryptStatePayload(JSONObject envelope, String encKeyHex, String macKeyHex) throws Exception {{
        String nonce = envelope.optString("nonce", "");
        String cipher = envelope.optString("cipher", "");
        String mac = envelope.optString("mac", "");
        if (nonce.isEmpty() || cipher.isEmpty() || mac.isEmpty()) {{
            throw new Exception("INVALID_ENVELOPE");
        }}
        String macInput = macKeyHex + ":" + nonce + ":" + cipher;
        String expectedMac = bytesToHex(sha256Bytes(macInput.getBytes(StandardCharsets.UTF_8)));
        if (!expectedMac.equals(mac)) {{
            throw new Exception("WRONG_PASSWORD");
        }}
        byte[] cipherBytes = hexToBytes(cipher);
        byte[] plainBytes = new byte[cipherBytes.length];
        for (int blockIdx = 0; blockIdx * 32 < cipherBytes.length; blockIdx++) {{
            String ksInput = encKeyHex + ":" + nonce + ":" + blockIdx;
            byte[] ks = sha256Bytes(ksInput.getBytes(StandardCharsets.UTF_8));
            int offset = blockIdx * 32;
            for (int j = 0; j < 32 && offset + j < cipherBytes.length; j++) {{
                plainBytes[offset + j] = (byte) (cipherBytes[offset + j] ^ ks[j]);
            }}
        }}
        String jsonStr = new String(plainBytes, StandardCharsets.UTF_8);
        return new JSONObject(jsonStr);
    }}

    public static JSONObject encryptStatePayload(JSONObject plainObj, String encKeyHex, String macKeyHex) throws Exception {{
        byte[] plainBytes = plainObj.toString().getBytes(StandardCharsets.UTF_8);
        byte[] nonceBytes = new byte[16];
        new SecureRandom().nextBytes(nonceBytes);
        String nonceHex = bytesToHex(nonceBytes);
        byte[] cipherBytes = new byte[plainBytes.length];

        for (int blockIdx = 0; blockIdx * 32 < plainBytes.length; blockIdx++) {{
            String ksInput = encKeyHex + ":" + nonceHex + ":" + blockIdx;
            byte[] ks = sha256Bytes(ksInput.getBytes(StandardCharsets.UTF_8));
            int offset = blockIdx * 32;
            for (int j = 0; j < 32 && offset + j < plainBytes.length; j++) {{
                cipherBytes[offset + j] = (byte) (plainBytes[offset + j] ^ ks[j]);
            }}
        }}

        String cipherHex = bytesToHex(cipherBytes);
        String macInput = macKeyHex + ":" + nonceHex + ":" + cipherHex;
        String macHex = bytesToHex(sha256Bytes(macInput.getBytes(StandardCharsets.UTF_8)));
        String verifyTag = bytesToHex(sha256Bytes(("verify:" + macKeyHex).getBytes(StandardCharsets.UTF_8)));

        JSONObject env = new JSONObject();
        env.put("v", 4);
        env.put("changeId", plainObj.optString("changeId", "chg_" + System.currentTimeMillis()));
        env.put("nonce", nonceHex);
        env.put("cipher", cipherHex);
        env.put("mac", macHex);
        env.put("verifyTag", verifyTag);
        env.put("updatedAt", plainObj.optLong("updatedAt", System.currentTimeMillis()));
        return env;
    }}

    public static JSONObject fetchFirebaseEnvelope(String fbUrl, String vaultKey) {{
        try {{
            URL url = new URL(fbUrl + "/vaults/" + vaultKey + ".json?_=" + System.currentTimeMillis());
            HttpURLConnection conn = (HttpURLConnection) url.openConnection();
            conn.setRequestMethod("GET");
            conn.setConnectTimeout(7000);
            conn.setReadTimeout(7000);
            if (conn.getResponseCode() == 200) {{
                BufferedReader br = new BufferedReader(new InputStreamReader(conn.getInputStream(), StandardCharsets.UTF_8));
                StringBuilder sb = new StringBuilder();
                String line;
                while ((line = br.readLine()) != null) sb.append(line);
                br.close();
                String raw = sb.toString().trim();
                if (!raw.isEmpty() && !raw.equals("null")) {{
                    return new JSONObject(raw);
                }}
            }}
        }} catch (Exception ignored) {{}}
        return null;
    }}

    public static boolean pushFirebaseEnvelope(String fbUrl, String vaultKey, JSONObject envelope) {{
        try {{
            URL url = new URL(fbUrl + "/vaults/" + vaultKey + ".json");
            HttpURLConnection conn = (HttpURLConnection) url.openConnection();
            conn.setRequestMethod("PUT");
            conn.setRequestProperty("Content-Type", "application/json; charset=UTF-8");
            conn.setConnectTimeout(7000);
            conn.setReadTimeout(7000);
            conn.setDoOutput(true);
            byte[] body = envelope.toString().getBytes(StandardCharsets.UTF_8);
            OutputStream os = conn.getOutputStream();
            os.write(body);
            os.flush();
            os.close();
            int code = conn.getResponseCode();
            return code >= 200 && code < 300;
        }} catch (Exception ignored) {{
            return false;
        }}
    }}
}}
""",
    )

    # 7. Java Source: WidgetDataStore.java (SharedPreferences + Optimistic Toggle + Background Firebase Sync)
    write_text(
        os.path.join(src_dir, "WidgetDataStore.java"),
        f"""package {PACKAGE_NAME};

import android.content.Context;
import android.content.SharedPreferences;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;
import org.json.JSONArray;
import org.json.JSONObject;

public class WidgetDataStore {{
    private static final String PREFS_NAME = "one_minor_one_major_widget_prefs";
    private static final String KEY_STATE_JSON = "state_json";
    private static final String KEY_AUTH_JSON = "auth_json";
    private static final String KEY_SNAPSHOT_JSON = "snapshot_json";
    private static final String KEY_ACTIVE_TAB = "active_tab";
    private static final String KEY_PENDING_ACTIONS = "pending_actions";

    public static SharedPreferences prefs(Context ctx) {{
        return ctx.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE);
    }}

    public static String getActiveTab(Context ctx) {{
        return prefs(ctx).getString(KEY_ACTIVE_TAB, "daily");
    }}

    public static void setActiveTab(Context ctx, String tab) {{
        prefs(ctx).edit().putString(KEY_ACTIVE_TAB, tab).apply();
    }}

    public static void saveFromWeb(Context ctx, String stateJson, String authJson, String snapshotJson) {{
        SharedPreferences.Editor ed = prefs(ctx).edit();
        if (stateJson != null && !stateJson.isEmpty()) ed.putString(KEY_STATE_JSON, stateJson);
        if (authJson != null && !authJson.isEmpty()) ed.putString(KEY_AUTH_JSON, authJson);
        if (snapshotJson != null && !snapshotJson.isEmpty()) ed.putString(KEY_SNAPSHOT_JSON, snapshotJson);
        ed.apply();
    }}

    public static JSONObject getSnapshot(Context ctx) {{
        String raw = prefs(ctx).getString(KEY_SNAPSHOT_JSON, "");
        if (raw != null && !raw.isEmpty()) {{
            try {{
                return new JSONObject(raw);
            }} catch (Exception ignored) {{}}
        }}
        return null;
    }}

    public static String consumePendingActions(Context ctx) {{
        SharedPreferences p = prefs(ctx);
        String raw = p.getString(KEY_PENDING_ACTIONS, "[]");
        p.edit().putString(KEY_PENDING_ACTIONS, "[]").apply();
        return raw;
    }}

    public static String getSavedStateJson(Context ctx) {{
        return prefs(ctx).getString(KEY_STATE_JSON, "");
    }}

    public static String getSavedAuthJson(Context ctx) {{
        return prefs(ctx).getString(KEY_AUTH_JSON, "");
    }}

    public static void toggleItemOptimisticAndSync(final Context ctx, final String itemType, final String itemId, final String dateStr) {{
        if (itemId == null || itemId.isEmpty()) return;
        SharedPreferences p = prefs(ctx);

        // 1. Append to pending actions queue so WebView applies exact scheduler rules when opened
        try {{
            JSONArray q = new JSONArray(p.getString(KEY_PENDING_ACTIONS, "[]"));
            JSONObject act = new JSONObject();
            act.put("type", "habit".equals(itemType) ? "toggle_habit" : "toggle_task");
            act.put("id", itemId);
            act.put("dateStr", dateStr != null ? dateStr : todayStr());
            act.put("ts", System.currentTimeMillis());
            q.put(act);
            p.edit().putString(KEY_PENDING_ACTIONS, q.toString()).apply();
        }} catch (Exception ignored) {{}}

        // 2. Immediately flip the item's 'done' state inside snapshot_json for <20ms wallpaper feedback
        boolean newDoneState = true;
        try {{
            JSONObject snap = getSnapshot(ctx);
            if (snap != null) {{
                if ("habit".equals(itemType)) {{
                    JSONObject daily = snap.optJSONObject("daily");
                    if (daily != null) {{
                        JSONArray habits = daily.optJSONArray("habits");
                        if (habits != null) {{
                            for (int i = 0; i < habits.length(); i++) {{
                                JSONObject h = habits.getJSONObject(i);
                                if (itemId.equals(h.optString("id"))) {{
                                    newDoneState = !h.optBoolean("done", false);
                                    h.put("done", newDoneState);
                                }}
                            }}
                        }}
                    }}
                    JSONArray allHabits = snap.optJSONArray("habits");
                    if (allHabits != null) {{
                        for (int i = 0; i < allHabits.length(); i++) {{
                            JSONObject h = allHabits.getJSONObject(i);
                            if (itemId.equals(h.optString("id"))) {{
                                h.put("done", newDoneState);
                            }}
                        }}
                    }}
                }} else {{
                    // Toggle in daily minor/major
                    JSONObject daily = snap.optJSONObject("daily");
                    if (daily != null) {{
                        JSONObject minObj = daily.optJSONObject("minor");
                        if (minObj != null && itemId.equals(minObj.optString("id"))) {{
                            newDoneState = !minObj.optBoolean("done", false);
                            minObj.put("done", newDoneState);
                        }}
                        JSONObject majObj = daily.optJSONObject("major");
                        if (majObj != null && itemId.equals(majObj.optString("id"))) {{
                            newDoneState = !majObj.optBoolean("done", false);
                            majObj.put("done", newDoneState);
                        }}
                    }}
                    // Toggle in weekly days
                    JSONArray weekly = snap.optJSONArray("weekly");
                    if (weekly != null) {{
                        for (int i = 0; i < weekly.length(); i++) {{
                            JSONObject day = weekly.getJSONObject(i);
                            JSONObject minObj = day.optJSONObject("minor");
                            if (minObj != null && itemId.equals(minObj.optString("id"))) {{
                                newDoneState = !minObj.optBoolean("done", false);
                                minObj.put("done", newDoneState);
                            }}
                            JSONObject majObj = day.optJSONObject("major");
                            if (majObj != null && itemId.equals(majObj.optString("id"))) {{
                                newDoneState = !majObj.optBoolean("done", false);
                                majObj.put("done", newDoneState);
                            }}
                        }}
                    }}
                    // Toggle in tasks list
                    JSONArray tasks = snap.optJSONArray("tasks");
                    if (tasks != null) {{
                        for (int i = 0; i < tasks.length(); i++) {{
                            JSONObject t = tasks.getJSONObject(i);
                            if (itemId.equals(t.optString("id"))) {{
                                newDoneState = !t.optBoolean("done", false);
                                t.put("done", newDoneState);
                            }}
                        }}
                    }}
                }}
                p.edit().putString(KEY_SNAPSHOT_JSON, snap.toString()).apply();
            }}
        }} catch (Exception ignored) {{}}

        // 3. Also notify MainActivity if it's alive in memory so WebView runs full auto-scheduler
        MainActivity.notifyWidgetActionFromBackground();

        // 4. Also push updated state directly to Firebase in background thread
        final boolean finalDone = newDoneState;
        new Thread(new Runnable() {{
            @Override
            public void run() {{
                syncToggleToFirebase(ctx, itemType, itemId, dateStr, finalDone);
            }}
        }}).start();
    }}

    private static void syncToggleToFirebase(Context ctx, String itemType, String itemId, String dateStr, boolean isDone) {{
        try {{
            SharedPreferences p = prefs(ctx);
            String authRaw = p.getString(KEY_AUTH_JSON, "");
            String stateRaw = p.getString(KEY_STATE_JSON, "");
            if (authRaw.isEmpty() || stateRaw.isEmpty()) return;

            JSONObject auth = new JSONObject(authRaw);
            String fbUrl = auth.optString("firebaseDbUrl", "https://one-minor-one-major-default-rtdb.firebaseio.com");
            String vaultKey = auth.optString("vaultKey", "");
            String encKeyHex = auth.optString("encKeyHex", "");
            String macKeyHex = auth.optString("macKeyHex", "");
            if (vaultKey.isEmpty() || encKeyHex.isEmpty() || macKeyHex.isEmpty()) return;

            JSONObject state = new JSONObject(stateRaw);
            String dStr = (dateStr != null && !dateStr.isEmpty()) ? dateStr : todayStr();

            if ("habit".equals(itemType)) {{
                JSONObject hc = state.optJSONObject("habitCompletions");
                if (hc == null) {{
                    hc = new JSONObject();
                    state.put("habitCompletions", hc);
                }}
                hc.put(dStr + "_" + itemId, isDone);
            }} else {{
                JSONArray tasks = state.optJSONArray("tasks");
                if (tasks != null) {{
                    for (int i = 0; i < tasks.length(); i++) {{
                        JSONObject t = tasks.getJSONObject(i);
                        if (itemId.equals(t.optString("id"))) {{
                            t.put("status", isDone ? "completed" : "active");
                            t.put("completedAt", isDone ? System.currentTimeMillis() : JSONObject.NULL);
                            break;
                        }}
                    }}
                }}
            }}

            JSONObject snap = getSnapshot(ctx);
            if (snap != null) {{
                state.put("widgetSnapshot", snap);
            }}
            state.put("updatedAt", System.currentTimeMillis());
            state.put("changeId", "chg_w_" + System.currentTimeMillis());
            p.edit().putString(KEY_STATE_JSON, state.toString()).apply();

            JSONObject env = VaultCrypto.encryptStatePayload(state, encKeyHex, macKeyHex);
            VaultCrypto.pushFirebaseEnvelope(fbUrl, vaultKey, env);
        }} catch (Exception ignored) {{}}
    }}

    public static void pullLatestFromFirebaseAsync(final Context ctx, final Runnable onComplete) {{
        new Thread(new Runnable() {{
            @Override
            public void run() {{
                try {{
                    SharedPreferences p = prefs(ctx);
                    String authRaw = p.getString(KEY_AUTH_JSON, "");
                    if (!authRaw.isEmpty()) {{
                        JSONObject auth = new JSONObject(authRaw);
                        String fbUrl = auth.optString("firebaseDbUrl", "https://one-minor-one-major-default-rtdb.firebaseio.com");
                        String vaultKey = auth.optString("vaultKey", "");
                        String encKeyHex = auth.optString("encKeyHex", "");
                        String macKeyHex = auth.optString("macKeyHex", "");
                        if (!vaultKey.isEmpty() && !encKeyHex.isEmpty() && !macKeyHex.isEmpty()) {{
                            JSONObject env = VaultCrypto.fetchFirebaseEnvelope(fbUrl, vaultKey);
                            if (env != null) {{
                                JSONObject remoteState = VaultCrypto.decryptStatePayload(env, encKeyHex, macKeyHex);
                                if (remoteState != null) {{
                                    SharedPreferences.Editor ed = p.edit();
                                    ed.putString(KEY_STATE_JSON, remoteState.toString());
                                    JSONObject snap = remoteState.optJSONObject("widgetSnapshot");
                                    if (snap != null) {{
                                        ed.putString(KEY_SNAPSHOT_JSON, snap.toString());
                                    }}
                                    ed.apply();
                                }}
                            }}
                        }}
                    }}
                }} catch (Exception ignored) {{}}
                if (onComplete != null) onComplete.run();
            }}
        }}).start();
    }}

    public static String todayStr() {{
        return new SimpleDateFormat("yyyy-MM-dd", Locale.US).format(new Date());
    }}
}}
""",
    )

    # 8. Java Source: PlannerWidgetProvider.java (AppWidgetProvider handling Tabs, Checkboxes & Updates)
    write_text(
        os.path.join(src_dir, "PlannerWidgetProvider.java"),
        f"""package {PACKAGE_NAME};

import android.app.PendingIntent;
import android.appwidget.AppWidgetManager;
import android.appwidget.AppWidgetProvider;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.net.Uri;
import android.widget.RemoteViews;
import org.json.JSONObject;

public class PlannerWidgetProvider extends AppWidgetProvider {{
    public static final String ACTION_SWITCH_TAB = "{PACKAGE_NAME}.ACTION_SWITCH_TAB";
    public static final String ACTION_ROW_CLICK = "{PACKAGE_NAME}.ACTION_ROW_CLICK";
    public static final String ACTION_REFRESH_WIDGET = "{PACKAGE_NAME}.ACTION_REFRESH_WIDGET";

    public static final String EXTRA_TAB = "extra_tab";
    public static final String EXTRA_CLICK_MODE = "extra_click_mode";
    public static final String EXTRA_ITEM_TYPE = "extra_item_type";
    public static final String EXTRA_ITEM_ID = "extra_item_id";
    public static final String EXTRA_DATE_STR = "extra_date_str";
    public static final String EXTRA_EDIT_ID = "extra_edit_id";

    @Override
    public void onUpdate(Context context, AppWidgetManager appWidgetManager, int[] appWidgetIds) {{
        updateAllWidgets(context);
    }}

    @Override
    public void onReceive(final Context context, Intent intent) {{
        super.onReceive(context, intent);
        if (intent == null || intent.getAction() == null) return;
        String action = intent.getAction();

        if (ACTION_SWITCH_TAB.equals(action)) {{
            String tab = intent.getStringExtra(EXTRA_TAB);
            if (tab != null && !tab.isEmpty()) {{
                WidgetDataStore.setActiveTab(context, tab);
                updateAllWidgets(context);
            }}
        }} else if (ACTION_ROW_CLICK.equals(action)) {{
            String clickMode = intent.getStringExtra(EXTRA_CLICK_MODE);
            if ("toggle".equals(clickMode)) {{
                String itemType = intent.getStringExtra(EXTRA_ITEM_TYPE);
                String itemId = intent.getStringExtra(EXTRA_ITEM_ID);
                String dateStr = intent.getStringExtra(EXTRA_DATE_STR);
                if (itemId != null && !itemId.isEmpty()) {{
                    WidgetDataStore.toggleItemOptimisticAndSync(context, itemType, itemId, dateStr);
                    updateAllWidgets(context);
                }} else {{
                    Intent openIntent = new Intent(context, MainActivity.class);
                    openIntent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);
                    context.startActivity(openIntent);
                }}
            }} else {{
                Intent openIntent = new Intent(context, MainActivity.class);
                openIntent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);
                String editId = intent.getStringExtra(EXTRA_EDIT_ID);
                if (editId != null && !editId.isEmpty()) {{
                    openIntent.putExtra("widgetEditId", editId);
                }}
                openIntent.putExtra("widgetView", WidgetDataStore.getActiveTab(context));
                context.startActivity(openIntent);
            }}
        }} else if (ACTION_REFRESH_WIDGET.equals(action)) {{
            WidgetDataStore.pullLatestFromFirebaseAsync(context, new Runnable() {{
                @Override
                public void run() {{
                    updateAllWidgets(context);
                }}
            }});
        }}
    }}

    public static void updateAllWidgets(Context context) {{
        AppWidgetManager mgr = AppWidgetManager.getInstance(context);
        ComponentName cn = new ComponentName(context, PlannerWidgetProvider.class);
        int[] ids = mgr.getAppWidgetIds(cn);
        if (ids == null || ids.length == 0) return;

        String activeTab = WidgetDataStore.getActiveTab(context);
        JSONObject snap = WidgetDataStore.getSnapshot(context);
        String headerTitle = "1 Minor + 1 Major";
        if (snap != null) {{
            String th = snap.optString("todayHeader", "");
            if (!th.isEmpty()) headerTitle = th;
        }}

        for (int appWidgetId : ids) {{
            RemoteViews rv = new RemoteViews(context.getPackageName(), R.layout.widget_planner);
            rv.setTextViewText(R.id.widget_date_title, headerTitle);

            // Style the 3 View Tabs (Daily | Weekly | Tasks)
            styleTab(rv, R.id.widget_tab_daily, "daily".equals(activeTab));
            styleTab(rv, R.id.widget_tab_weekly, "weekly".equals(activeTab));
            styleTab(rv, R.id.widget_tab_tasks, "tasks".equals(activeTab));

            rv.setOnClickPendingIntent(R.id.widget_tab_daily, makeTabIntent(context, "daily", 101));
            rv.setOnClickPendingIntent(R.id.widget_tab_weekly, makeTabIntent(context, "weekly", 102));
            rv.setOnClickPendingIntent(R.id.widget_tab_tasks, makeTabIntent(context, "tasks", 103));

            // Header Title click -> Open App in current view
            Intent openMain = new Intent(context, MainActivity.class);
            openMain.putExtra("widgetView", activeTab);
            openMain.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);
            PendingIntent piMain = PendingIntent.getActivity(
                context, 200, openMain, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE
            );
            rv.setOnClickPendingIntent(R.id.widget_date_title, piMain);
            rv.setOnClickPendingIntent(R.id.widget_empty_view, piMain);

            // '+' Button click -> Open App to Add Task
            Intent openAdd = new Intent(context, MainActivity.class);
            openAdd.putExtra("widgetView", "tasks");
            openAdd.putExtra("widgetNewTask", true);
            openAdd.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);
            PendingIntent piAdd = PendingIntent.getActivity(
                context, 201, openAdd, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE
            );
            rv.setOnClickPendingIntent(R.id.widget_btn_add, piAdd);

            // '↻' Refresh Button click
            Intent refIntent = new Intent(context, PlannerWidgetProvider.class);
            refIntent.setAction(ACTION_REFRESH_WIDGET);
            PendingIntent piRef = PendingIntent.getBroadcast(
                context, 202, refIntent, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE
            );
            rv.setOnClickPendingIntent(R.id.widget_btn_refresh, piRef);

            // Bind Scrollable ListView to PlannerWidgetService
            Intent svcIntent = new Intent(context, PlannerWidgetService.class);
            svcIntent.putExtra(AppWidgetManager.EXTRA_APPWIDGET_ID, appWidgetId);
            svcIntent.setData(Uri.parse(svcIntent.toUri(Intent.URI_INTENT_SCHEME)));
            rv.setRemoteAdapter(R.id.widget_list_view, svcIntent);
            rv.setEmptyView(R.id.widget_list_view, R.id.widget_empty_view);

            // Template PendingIntent for ListView row clicks (Checkbox toggles on wallpaper; Text opens app)
            Intent rowBroadcast = new Intent(context, PlannerWidgetProvider.class);
            rowBroadcast.setAction(ACTION_ROW_CLICK);
            PendingIntent piRowTemplate = PendingIntent.getBroadcast(
                context, 300, rowBroadcast, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_MUTABLE
            );
            rv.setPendingIntentTemplate(R.id.widget_list_view, piRowTemplate);

            mgr.updateAppWidget(appWidgetId, rv);
        }}
        mgr.notifyAppWidgetViewDataChanged(ids, R.id.widget_list_view);
    }}

    private static void styleTab(RemoteViews rv, int viewId, boolean active) {{
        rv.setInt(viewId, "setBackgroundResource", active ? R.drawable.bg_tab_active : R.drawable.bg_tab_inactive);
        rv.setTextColor(viewId, active ? 0xFFFFFFFF : 0xFF475569);
    }}

    private static PendingIntent makeTabIntent(Context context, String tab, int reqCode) {{
        Intent i = new Intent(context, PlannerWidgetProvider.class);
        i.setAction(ACTION_SWITCH_TAB);
        i.putExtra(EXTRA_TAB, tab);
        return PendingIntent.getBroadcast(
            context, reqCode, i, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE
        );
    }}
}}
""",
    )

    # 9. Java Source: PlannerWidgetService.java (RemoteViewsService + Factory for Daily / Weekly / Tasks)
    write_text(
        os.path.join(src_dir, "PlannerWidgetService.java"),
        f"""package {PACKAGE_NAME};

import android.content.Context;
import android.content.Intent;
import android.graphics.Paint;
import android.view.View;
import android.widget.RemoteViews;
import android.widget.RemoteViewsService;
import java.util.ArrayList;
import java.util.List;
import org.json.JSONArray;
import org.json.JSONObject;

public class PlannerWidgetService extends RemoteViewsService {{
    @Override
    public RemoteViewsFactory onGetViewFactory(Intent intent) {{
        return new PlannerRemoteViewsFactory(this.getApplicationContext());
    }}

    private static class RowEntry {{
        boolean isHeader;
        String headerText;
        int headerColor;

        String itemType; // "task" or "habit"
        String itemId;
        String dateStr;
        String title;
        String subtitle;
        boolean done;
        boolean empty;

        static RowEntry header(String text, int color) {{
            RowEntry r = new RowEntry();
            r.isHeader = true;
            r.headerText = text;
            r.headerColor = color;
            return r;
        }}

        static RowEntry item(String type, String id, String dateStr, String title, String subtitle, boolean done, boolean empty) {{
            RowEntry r = new RowEntry();
            r.isHeader = false;
            r.itemType = type;
            r.itemId = id != null ? id : "";
            r.dateStr = dateStr != null ? dateStr : "";
            r.title = title != null ? title : "";
            r.subtitle = subtitle != null ? subtitle : "";
            r.done = done;
            r.empty = empty;
            return r;
        }}
    }}

    private static class PlannerRemoteViewsFactory implements RemoteViewsService.RemoteViewsFactory {{
        private final Context context;
        private final List<RowEntry> rows = new ArrayList<>();

        PlannerRemoteViewsFactory(Context context) {{
            this.context = context;
        }}

        @Override
        public void onCreate() {{
            rebuildRows();
        }}

        @Override
        public void onDataSetChanged() {{
            rebuildRows();
        }}

        private void rebuildRows() {{
            rows.clear();
            JSONObject snap = WidgetDataStore.getSnapshot(context);
            if (snap == null) return;

            String tab = WidgetDataStore.getActiveTab(context);
            String todayStr = snap.optString("todayStr", WidgetDataStore.todayStr());

            if ("daily".equals(tab)) {{
                JSONObject daily = snap.optJSONObject("daily");
                if (daily == null) return;

                JSONArray habits = daily.optJSONArray("habits");
                if (habits != null && habits.length() > 0) {{
                    rows.add(RowEntry.header("🔄 HABITS", 0xFF475569));
                    for (int i = 0; i < habits.length(); i++) {{
                        JSONObject h = habits.optJSONObject(i);
                        if (h != null) {{
                            rows.add(RowEntry.item(
                                "habit",
                                h.optString("id"),
                                h.optString("dateStr", todayStr),
                                h.optString("title"),
                                "",
                                h.optBoolean("done", false),
                                false
                            ));
                        }}
                    }}
                }}

                rows.add(RowEntry.header("✓ 1 MINOR THING", 0xFF047857));
                JSONObject minObj = daily.optJSONObject("minor");
                if (minObj != null) {{
                    rows.add(RowEntry.item(
                        "task",
                        minObj.optString("id"),
                        minObj.optString("dateStr", todayStr),
                        minObj.optString("title"),
                        minObj.optString("subtitle"),
                        minObj.optBoolean("done", false),
                        minObj.optBoolean("empty", false)
                    ));
                }}

                rows.add(RowEntry.header("★ 1 MAJOR THING", 0xFF1D4ED8));
                JSONObject majObj = daily.optJSONObject("major");
                if (majObj != null) {{
                    rows.add(RowEntry.item(
                        "task",
                        majObj.optString("id"),
                        majObj.optString("dateStr", todayStr),
                        majObj.optString("title"),
                        majObj.optString("subtitle"),
                        majObj.optBoolean("done", false),
                        majObj.optBoolean("empty", false)
                    ));
                }}

            }} else if ("weekly".equals(tab)) {{
                JSONArray weekly = snap.optJSONArray("weekly");
                if (weekly == null) return;
                for (int i = 0; i < weekly.length(); i++) {{
                    JSONObject day = weekly.optJSONObject(i);
                    if (day == null) continue;
                    boolean isToday = day.optBoolean("isToday", false);
                    String dStr = day.optString("dateStr", todayStr);
                    rows.add(RowEntry.header(
                        day.optString("dayLabel", dStr),
                        isToday ? 0xFF1D4ED8 : 0xFF334155
                    ));

                    JSONObject minObj = day.optJSONObject("minor");
                    if (minObj != null) {{
                        String badge = minObj.optString("recBadge", "");
                        rows.add(RowEntry.item(
                            "task",
                            minObj.optString("id"),
                            dStr,
                            "✓ " + minObj.optString("title"),
                            badge.isEmpty() ? "Minor Slot" : "Minor • " + badge,
                            minObj.optBoolean("done", false),
                            false
                        ));
                    }} else {{
                        rows.add(RowEntry.item("task", "", dStr, "✓ — Empty Minor Slot —", "", false, true));
                    }}

                    JSONObject majObj = day.optJSONObject("major");
                    if (majObj != null) {{
                        String badge = majObj.optString("recBadge", "");
                        rows.add(RowEntry.item(
                            "task",
                            majObj.optString("id"),
                            dStr,
                            "★ " + majObj.optString("title"),
                            badge.isEmpty() ? "Major Slot" : "Major • " + badge,
                            majObj.optBoolean("done", false),
                            false
                        ));
                    }} else {{
                        rows.add(RowEntry.item("task", "", dStr, "★ — Empty Major Slot —", "", false, true));
                    }}
                }}

            }} else {{
                // "tasks" mode (Microsoft To Do / Google Tasks style list)
                JSONArray tasks = snap.optJSONArray("tasks");
                if (tasks != null && tasks.length() > 0) {{
                    rows.add(RowEntry.header("📋 ACTIVE TASKS (" + tasks.length() + ")", 0xFF1D4ED8));
                    for (int i = 0; i < tasks.length(); i++) {{
                        JSONObject t = tasks.optJSONObject(i);
                        if (t != null) {{
                            rows.add(RowEntry.item(
                                "task",
                                t.optString("id"),
                                t.optString("dateStr", todayStr),
                                t.optString("title"),
                                t.optString("subtitle"),
                                t.optBoolean("done", false),
                                false
                            ));
                        }}
                    }}
                }}

                JSONArray habits = snap.optJSONArray("habits");
                if (habits != null && habits.length() > 0) {{
                    rows.add(RowEntry.header("🔄 HABITS (" + habits.length() + ")", 0xFF047857));
                    for (int i = 0; i < habits.length(); i++) {{
                        JSONObject h = habits.optJSONObject(i);
                        if (h != null) {{
                            rows.add(RowEntry.item(
                                "habit",
                                h.optString("id"),
                                h.optString("dateStr", todayStr),
                                h.optString("title"),
                                h.optString("subtitle"),
                                h.optBoolean("done", false),
                                false
                            ));
                        }}
                    }}
                }}
            }}
        }}

        @Override
        public void onDestroy() {{
            rows.clear();
        }}

        @Override
        public int getCount() {{
            return rows.size();
        }}

        @Override
        public int getViewTypeCount() {{
            return 2;
        }}

        @Override
        public int getItemViewType(int position) {{
            if (position < 0 || position >= rows.size()) return 1;
            return rows.get(position).isHeader ? 0 : 1;
        }}

        @Override
        public RemoteViews getViewAt(int position) {{
            if (position < 0 || position >= rows.size()) return null;
            RowEntry r = rows.get(position);

            if (r.isHeader) {{
                RemoteViews rv = new RemoteViews(context.getPackageName(), R.layout.widget_row_header);
                rv.setTextViewText(R.id.row_header_text, r.headerText);
                rv.setTextColor(R.id.row_header_text, r.headerColor);
                return rv;
            }}

            RemoteViews rv = new RemoteViews(context.getPackageName(), R.layout.widget_row_item);
            rv.setTextViewText(R.id.row_item_title, r.title);
            rv.setTextColor(R.id.row_item_title, r.empty ? 0xFF94A3B8 : (r.done ? 0xFF64748B : 0xFF0F172A));
            rv.setInt(
                R.id.row_item_title,
                "setPaintFlags",
                r.done ? (Paint.STRIKE_THRU_TEXT_FLAG | Paint.ANTI_ALIAS_FLAG) : Paint.ANTI_ALIAS_FLAG
            );

            if (r.subtitle != null && !r.subtitle.isEmpty()) {{
                rv.setViewVisibility(R.id.row_item_subtitle, View.VISIBLE);
                rv.setTextViewText(R.id.row_item_subtitle, r.subtitle);
            }} else {{
                rv.setViewVisibility(R.id.row_item_subtitle, View.GONE);
            }}

            if (r.empty) {{
                rv.setViewVisibility(R.id.row_check_TouchArea, View.GONE);
            }} else {{
                rv.setViewVisibility(R.id.row_check_TouchArea, View.VISIBLE);
                rv.setTextViewText(R.id.row_check_box, r.done ? "✓" : "");
                rv.setInt(
                    R.id.row_check_box,
                    "setBackgroundResource",
                    r.done ? R.drawable.bg_check_checked : R.drawable.bg_check_unchecked
                );
            }}

            // 1. Checkbox Fill-In Intent -> Checks off task directly on wallpaper without opening app!
            Intent toggleFill = new Intent();
            toggleFill.putExtra(PlannerWidgetProvider.EXTRA_CLICK_MODE, "toggle");
            toggleFill.putExtra(PlannerWidgetProvider.EXTRA_ITEM_TYPE, r.itemType);
            toggleFill.putExtra(PlannerWidgetProvider.EXTRA_ITEM_ID, r.itemId);
            toggleFill.putExtra(PlannerWidgetProvider.EXTRA_DATE_STR, r.dateStr);
            rv.setOnClickFillInIntent(R.id.row_check_TouchArea, toggleFill);

            // 2. Text Area Fill-In Intent -> Opens the app to view/edit task
            Intent openFill = new Intent();
            openFill.putExtra(PlannerWidgetProvider.EXTRA_CLICK_MODE, "open");
            openFill.putExtra(PlannerWidgetProvider.EXTRA_EDIT_ID, r.itemId);
            rv.setOnClickFillInIntent(R.id.row_text_area, openFill);

            return rv;
        }}

        @Override
        public RemoteViews getLoadingView() {{
            return null;
        }}

        @Override
        public long getItemId(int position) {{
            return position;
        }}

        @Override
        public boolean hasStableIds() {{
            return false;
        }}
    }}
}}
""",
    )

    # 10. Java Source: MainActivity.java (Full-Screen WebView + JavascriptInterface Bridge to Widget)
    write_text(
        os.path.join(src_dir, "MainActivity.java"),
        f"""package {PACKAGE_NAME};

import android.annotation.SuppressLint;
import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.webkit.JavascriptInterface;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

public class MainActivity extends Activity {{
    private static MainActivity activeInstance;
    private WebView webView;
    private boolean pageLoaded = false;

    private static final String LIVE_APP_URL = "https://robertbailey-tohka.github.io/one-major-one-minor/";
    private static final String LOCAL_ASSET_URL = "file:///android_asset/index.html";

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    protected void onCreate(Bundle savedInstanceState) {{
        super.onCreate(savedInstanceState);
        activeInstance = this;

        webView = new WebView(this);
        setContentView(webView);

        WebSettings ws = webView.getSettings();
        ws.setJavaScriptEnabled(true);
        ws.setDomStorageEnabled(true);
        ws.setDatabaseEnabled(true);
        ws.setAllowFileAccess(true);
        ws.setAllowContentAccess(true);
        ws.setCacheMode(WebSettings.LOAD_DEFAULT);

        webView.addJavascriptInterface(new AndroidWidgetBridge(), "AndroidWidgetBridge");
        webView.setWebChromeClient(new WebChromeClient());
        webView.setWebViewClient(new WebViewClient() {{
            @Override
            public void onPageFinished(WebView view, String url) {{
                super.onPageFinished(view, url);
                pageLoaded = true;
                forwardIntentToWeb(getIntent());
            }}

            @Override
            public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {{
                if (request != null && request.isForMainFrame()) {{
                    view.loadUrl(LOCAL_ASSET_URL);
                }}
            }}
        }});

        webView.loadUrl(LIVE_APP_URL);
    }}

    @Override
    protected void onNewIntent(Intent intent) {{
        super.onNewIntent(intent);
        setIntent(intent);
        if (pageLoaded) {{
            forwardIntentToWeb(intent);
        }}
    }}

    @Override
    protected void onResume() {{
        super.onResume();
        activeInstance = this;
        if (pageLoaded && webView != null) {{
            webView.evaluateJavascript("if(window.applyPendingNativeWidgetActions) window.applyPendingNativeWidgetActions();", null);
        }}
    }}

    @Override
    protected void onDestroy() {{
        if (activeInstance == this) activeInstance = null;
        super.onDestroy();
    }}

    private void forwardIntentToWeb(Intent intent) {{
        if (intent == null || webView == null) return;
        final String viewMode = intent.getStringExtra("widgetView");
        final String editId = intent.getStringExtra("widgetEditId");
        final boolean newTask = intent.getBooleanExtra("widgetNewTask", false);

        webView.evaluateJavascript("if(window.applyPendingNativeWidgetActions) window.applyPendingNativeWidgetActions();", null);
        if (viewMode != null || editId != null || newTask) {{
            String js = String.format(
                "if(window.handleWidgetLaunchParams) window.handleWidgetLaunchParams(%s, %s, %s);",
                viewMode != null ? "'" + viewMode.replace("'", "") + "'" : "null",
                editId != null && !editId.isEmpty() ? "'" + editId.replace("'", "") + "'" : "null",
                newTask ? "true" : "false"
            );
            webView.evaluateJavascript(js, null);
            intent.removeExtra("widgetView");
            intent.removeExtra("widgetEditId");
            intent.removeExtra("widgetNewTask");
        }}
    }}

    public static void notifyWidgetActionFromBackground() {{
        final MainActivity inst = activeInstance;
        if (inst != null && inst.webView != null && inst.pageLoaded) {{
            new Handler(Looper.getMainLooper()).post(new Runnable() {{
                @Override
                public void run() {{
                    inst.webView.evaluateJavascript("if(window.applyPendingNativeWidgetActions) window.applyPendingNativeWidgetActions();", null);
                }}
            }});
        }}
    }}

    @Override
    public void onBackPressed() {{
        if (webView != null && webView.canGoBack()) {{
            webView.goBack();
        }} else {{
            super.onBackPressed();
        }}
    }}

    public class AndroidWidgetBridge {{
        @JavascriptInterface
        public void syncFromWeb(String stateJson, String authJson, String snapshotJson) {{
            WidgetDataStore.saveFromWeb(MainActivity.this, stateJson, authJson, snapshotJson);
            PlannerWidgetProvider.updateAllWidgets(MainActivity.this);
        }}

        @JavascriptInterface
        public String consumePendingActions() {{
            return WidgetDataStore.consumePendingActions(MainActivity.this);
        }}

        @JavascriptInterface
        public String getSavedStateJson() {{
            return WidgetDataStore.getSavedStateJson(MainActivity.this);
        }}

        @JavascriptInterface
        public String getSavedAuthJson() {{
            return WidgetDataStore.getSavedAuthJson(MainActivity.this);
        }}
    }}
}}
""",
    )


def run_cmd(cmd):
    print(">>", " ".join(cmd))
    subprocess.run(cmd, check=True)


def compile_apk():
    tools = find_sdk_tools()
    generate_project_files()

    compiled_res_zip = os.path.join(BUILD_DIR, "compiled_res.zip")
    unaligned_apk = os.path.join(BUILD_DIR, "unaligned.apk")
    aligned_apk = os.path.join(BUILD_DIR, "aligned.apk")
    gen_java_dir = os.path.join(BUILD_DIR, "gen")
    classes_dir = os.path.join(BUILD_DIR, "classes")
    dex_dir = os.path.join(BUILD_DIR, "dex")
    keystore_path = os.path.join(BUILD_DIR, "release.keystore")

    os.makedirs(gen_java_dir, exist_ok=True)
    os.makedirs(classes_dir, exist_ok=True)
    os.makedirs(dex_dir, exist_ok=True)

    # 1. Compile resources with aapt2
    run_cmd([
        tools["aapt2"], "compile",
        "--dir", os.path.join(BUILD_DIR, "res"),
        "-o", compiled_res_zip
    ])

    # 2. Link resources & generate R.java + base APK with assets
    run_cmd([
        tools["aapt2"], "link",
        "-o", unaligned_apk,
        "-I", tools["android_jar"],
        "--manifest", os.path.join(BUILD_DIR, "AndroidManifest.xml"),
        "-A", os.path.join(BUILD_DIR, "assets"),
        "--java", gen_java_dir,
        compiled_res_zip
    ])

    # 3. Compile Java sources + R.java
    java_files = []
    for root, _, files in os.walk(os.path.join(BUILD_DIR, "src")):
        for f in files:
            if f.endswith(".java"):
                java_files.append(os.path.join(root, f))
    for root, _, files in os.walk(gen_java_dir):
        for f in files:
            if f.endswith(".java"):
                java_files.append(os.path.join(root, f))

    run_cmd([
        "javac",
        "-source", "1.8",
        "-target", "1.8",
        "-encoding", "UTF-8",
        "-bootclasspath", tools["android_jar"],
        "-classpath", tools["android_jar"],
        "-d", classes_dir
    ] + java_files)

    # 4. Convert .class files to classes.dex using d8
    class_files = []
    for root, _, files in os.walk(classes_dir):
        for f in files:
            if f.endswith(".class"):
                class_files.append(os.path.join(root, f))

    run_cmd([
        tools["d8"],
        "--lib", tools["android_jar"],
        "--min-api", "26",
        "--output", dex_dir
    ] + class_files)

    # 5. Add classes.dex into unaligned.apk
    import zipfile
    with zipfile.ZipFile(unaligned_apk, "a", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.write(os.path.join(dex_dir, "classes.dex"), "classes.dex")

    # 6. Zipalign APK
    run_cmd([
        tools["zipalign"], "-f", "-p", "4",
        unaligned_apk, aligned_apk
    ])

    # 7. Generate signing keystore & sign APK (v1 + v2 + v3 signatures for all Android versions)
    run_cmd([
        "keytool", "-genkeypair",
        "-v",
        "-keystore", keystore_path,
        "-alias", "planner_key",
        "-keyalg", "RSA",
        "-keysize", "2048",
        "-validity", "10000",
        "-storepass", "planner123",
        "-keypass", "planner123",
        "-dname", "CN=OneMinorOneMajor, OU=Planner, O=RobertBailey, L=US, S=US, C=US"
    ])

    run_cmd([
        tools["apksigner"], "sign",
        "--ks", keystore_path,
        "--ks-key-alias", "planner_key",
        "--ks-pass", "pass:planner123",
        "--key-pass", "pass:planner123",
        "--out", OUT_APK,
        aligned_apk
    ])

    print(f"\nSUCCESS! Signed Android Widget APK built at: {OUT_APK} ({os.path.getsize(OUT_APK)} bytes)")


if __name__ == "__main__":
    compile_apk()
