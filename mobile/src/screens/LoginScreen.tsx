import { useState } from "react";
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  Alert,
  ActivityIndicator,
} from "react-native";
import { api } from "../api/client";
import { useAuthStore } from "../store/auth";

export default function LoginScreen() {
  const [username, setU] = useState("alcaldia");
  const [password, setP] = useState("Alcaldia2025!");
  const [loading, setLoading] = useState(false);
  const login = useAuthStore((s) => s.login);

  async function loginJson(user: string, pass: string) {
    return api.post("/auth/login", {
      username: user,
      password: pass,
    });
  }

  async function loginForm(user: string, pass: string) {
    const body = new URLSearchParams();
    body.append("username", user);
    body.append("password", pass);

    return api.post("/auth/login", body.toString(), {
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
      },
    });
  }

  async function submit() {
    const user = username.trim();
    const pass = password;

    if (!user || !pass) {
      Alert.alert("Error", "Ingrese usuario y contraseña");
      return;
    }

    setLoading(true);

    try {
      let response;

      try {
        response = await loginJson(user, pass);
      } catch {
        response = await loginForm(user, pass);
      }

      const token =
        response.data.access_token ||
        response.data.token ||
        response.data.accessToken;

      const rol = response.data.rol || response.data.role || "USUARIO";
      const nombre = response.data.nombre || response.data.name || user;

      if (!token) {
        Alert.alert("Error", "El backend respondió, pero no devolvió token.");
        return;
      }

      await login(token, rol, nombre);
    } catch (e: any) {
      const status = e.response?.status;
      const detail = e.response?.data?.detail || e.response?.data?.message;

      Alert.alert(
        "Error de login",
        `No se pudo iniciar sesión.\n\nEstado: ${status || "sin respuesta"}\nDetalle: ${
          detail || "Credenciales inválidas o backend no disponible"
        }`
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <View style={styles.c}>
      <Text style={styles.title}>SEMAPA</Text>
      <Text style={styles.subtitle}>Gestión Inteligente de Agua Potable</Text>

      <TextInput
        style={styles.in}
        value={username}
        onChangeText={setU}
        placeholder="Usuario"
        autoCapitalize="none"
        autoCorrect={false}
      />

      <TextInput
        style={styles.in}
        value={password}
        onChangeText={setP}
        placeholder="Contraseña"
        secureTextEntry
        autoCapitalize="none"
        autoCorrect={false}
      />

      <TouchableOpacity style={styles.btn} onPress={submit} disabled={loading}>
        {loading ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <Text style={styles.btnText}>Ingresar</Text>
        )}
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  c: {
    flex: 1,
    padding: 24,
    justifyContent: "center",
    backgroundColor: "#1287B1",
  },
  title: {
    fontSize: 36,
    fontWeight: "700",
    color: "#fff",
    textAlign: "center",
  },
  subtitle: {
    color: "#cfeefb",
    textAlign: "center",
    marginBottom: 32,
  },
  in: {
    backgroundColor: "#fff",
    padding: 12,
    borderRadius: 8,
    marginBottom: 12,
    fontSize: 16,
  },
  btn: {
    backgroundColor: "#0A4F66",
    padding: 14,
    borderRadius: 8,
    marginTop: 8,
    minHeight: 52,
    alignItems: "center",
    justifyContent: "center",
  },
  btnText: {
    color: "#fff",
    fontSize: 16,
    fontWeight: "700",
    textAlign: "center",
  },
});