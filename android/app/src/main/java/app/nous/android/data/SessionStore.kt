package app.nous.android.data

import android.content.Context
import android.content.SharedPreferences
import okhttp3.Cookie
import okhttp3.CookieJar
import okhttp3.HttpUrl
import org.json.JSONArray
import org.json.JSONObject

/**
 * Remembers the server address and the HttpOnly owner cookie.
 * The cookie is what lets a phone on the LAN past the Nous gate.
 */
class SessionStore(context: Context) {
    private val prefs = context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
    val cookies = PersistentCookieJar(prefs)

    var baseUrl: String?
        get() = prefs.getString(KEY_URL, null)?.takeIf { it.isNotBlank() }
        set(value) {
            prefs.edit().putString(KEY_URL, value?.trim()?.trimEnd('/')).apply()
        }

    fun clearCookies() {
        cookies.clear()
    }

    private companion object {
        const val PREFS = "nous"
        const val KEY_URL = "base_url"
    }
}

class PersistentCookieJar(private val prefs: SharedPreferences) : CookieJar {
    private val cookies = mutableListOf<Cookie>()

    init {
        try {
            load()
        } catch (_: Exception) {
            cookies.clear()
            prefs.edit().remove(KEY).apply()
        }
    }

    @Synchronized
    override fun saveFromResponse(url: HttpUrl, cookies: List<Cookie>) {
        val now = System.currentTimeMillis()
        for (cookie in cookies) {
            this.cookies.removeAll { it.name == cookie.name && it.domain == cookie.domain && it.path == cookie.path }
            if (cookie.expiresAt > now) this.cookies += cookie
        }
        save()
    }

    @Synchronized
    override fun loadForRequest(url: HttpUrl): List<Cookie> {
        val now = System.currentTimeMillis()
        if (cookies.removeAll { it.expiresAt <= now }) save()
        return cookies.filter { it.matches(url) }
    }

    @Synchronized
    fun clear() {
        cookies.clear()
        prefs.edit().remove(KEY).apply()
    }

    private fun load() {
        val raw = prefs.getString(KEY, null) ?: return
        val parsed = JSONArray(raw)
        val restored = mutableListOf<Cookie>()
        for (index in 0 until parsed.length()) {
            cookieFrom(parsed.getJSONObject(index))?.let(restored::add)
        }
        cookies.clear()
        cookies += restored
    }

    private fun save() {
        val encoded = JSONArray()
        for (cookie in cookies) {
            encoded.put(
                JSONObject()
                    .put("name", cookie.name)
                    .put("value", cookie.value)
                    .put("domain", cookie.domain)
                    .put("path", cookie.path)
                    .put("expiresAt", cookie.expiresAt)
                    .put("hostOnly", cookie.hostOnly)
                    .put("secure", cookie.secure)
                    .put("httpOnly", cookie.httpOnly),
            )
        }
        prefs.edit().putString(KEY, encoded.toString()).apply()
    }

    private fun cookieFrom(json: JSONObject): Cookie? {
        return try {
            val builder = Cookie.Builder()
                .name(json.getString("name"))
                .value(json.getString("value"))
                .path(json.optString("path", "/"))
                .expiresAt(json.optLong("expiresAt", Long.MAX_VALUE))
            val domain = json.getString("domain")
            if (json.optBoolean("hostOnly", true)) builder.hostOnlyDomain(domain) else builder.domain(domain)
            if (json.optBoolean("secure")) builder.secure()
            if (json.optBoolean("httpOnly")) builder.httpOnly()
            builder.build()
        } catch (_: Exception) {
            null
        }
    }

    private companion object {
        const val KEY = "cookies"
    }
}
