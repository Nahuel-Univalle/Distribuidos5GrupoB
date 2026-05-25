import { View, Text, TouchableOpacity, StyleSheet } from "react-native";
import { useAuthStore } from "../store/auth";

export default function HomeScreen({ navigation }: any) {
  const { nombre, rol, logout } = useAuthStore();

  return (
    <View style={styles.container}>
      <Text style={styles.title}>SEMAPA Móvil</Text>
      <Text style={styles.subtitle}>Usuario: {nombre}</Text>
      <Text style={styles.subtitle}>Rol: {rol}</Text>

      <TouchableOpacity style={styles.button} onPress={() => navigation.navigate("Lectura")}>
        <Text style={styles.buttonText}>Registrar lectura manual</Text>
      </TouchableOpacity>

      <TouchableOpacity style={styles.secondaryButton} onPress={() => navigation.navigate("Historial")}>
        <Text style={styles.buttonText}>Ver historial</Text>
      </TouchableOpacity>

      <TouchableOpacity style={styles.logoutButton} onPress={() => logout()}>
        <Text style={styles.buttonText}>Salir</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 24, justifyContent: "center", backgroundColor: "#f8fafc" },
  title: { fontSize: 28, fontWeight: "800", color: "#0f172a", marginBottom: 12, textAlign: "center" },
  subtitle: { fontSize: 16, color: "#475569", marginBottom: 6, textAlign: "center" },
  button: { backgroundColor: "#1287B1", padding: 15, borderRadius: 10, marginTop: 28 },
  secondaryButton: { backgroundColor: "#0f766e", padding: 15, borderRadius: 10, marginTop: 12 },
  logoutButton: { backgroundColor: "#94a3b8", padding: 15, borderRadius: 10, marginTop: 12 },
  buttonText: { color: "#fff", textAlign: "center", fontWeight: "800", fontSize: 16 },
});
