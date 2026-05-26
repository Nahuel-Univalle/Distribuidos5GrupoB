import { useState } from "react";
import { Text, TextInput, TouchableOpacity, StyleSheet, Alert, ScrollView, View } from "react-native";
import { api } from "../api/client";

export default function LecturaScreen() {
  const [contrato, setContrato] = useState("100021154");
  const [lectura, setLectura] = useState("");
  const [busy, setBusy] = useState(false);
  const [resultado, setResultado] = useState<any>(null);

  async function enviar() {
    const numeroContrato = parseInt(contrato, 10);
    const lecturaLitros = parseInt(lectura, 10);

    if (!contrato || Number.isNaN(numeroContrato)) {
      Alert.alert("Dato inválido", "Ingrese un número de contrato válido.");
      return;
    }

    if (!lectura || Number.isNaN(lecturaLitros) || lecturaLitros < 0) {
      Alert.alert("Dato inválido", "Ingrese una lectura numérica válida.");
      return;
    }

    setBusy(true);
    setResultado(null);

    try {
      const response = await api.post("/lecturas/manual", {
        numero_contrato: numeroContrato,
        lectura_litros: lecturaLitros,
        foto_url: "registro-manual-app-movil.jpg",
      });

      setResultado(response.data);
      Alert.alert("Lectura registrada", "La lectura manual fue guardada correctamente en SEMAPA.");
      setLectura("");
    } catch (e: any) {
      Alert.alert("Error", e.response?.data?.detail || "No se pudo registrar la lectura.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <Text style={styles.title}>Registro de lectura manual</Text>
      <Text style={styles.description}>
        Ingrese el contrato del medidor y la lectura actual en litros.
      </Text>

      <Text style={styles.label}>Número de contrato</Text>
      <TextInput
        style={styles.input}
        keyboardType="number-pad"
        value={contrato}
        onChangeText={setContrato}
        placeholder="Ej: 100021154"
      />

      <Text style={styles.label}>Lectura actual en litros</Text>
      <TextInput
        style={styles.input}
        keyboardType="number-pad"
        value={lectura}
        onChangeText={setLectura}
        placeholder="Ej: 123456"
      />

      <TouchableOpacity style={[styles.button, busy && styles.buttonDisabled]} disabled={busy} onPress={enviar}>
        <Text style={styles.buttonText}>{busy ? "Registrando..." : "Registrar lectura"}</Text>
      </TouchableOpacity>

      {resultado && (
        <View style={styles.resultBox}>
          <Text style={styles.resultTitle}>Registro exitoso</Text>
          <Text style={styles.resultText}>Medidor ID: {resultado.medidor_id}</Text>
          <Text style={styles.resultText}>Fecha: {resultado.timestamp}</Text>
        </View>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { padding: 24, backgroundColor: "#f8fafc", flexGrow: 1 },
  title: { fontSize: 22, fontWeight: "800", color: "#0f172a", marginBottom: 8 },
  description: { color: "#64748b", marginBottom: 24 },
  label: { fontWeight: "700", color: "#334155", marginBottom: 6 },
  input: {
    backgroundColor: "#fff",
    padding: 14,
    borderRadius: 10,
    borderColor: "#dbe4ee",
    borderWidth: 1,
    fontSize: 18,
    marginBottom: 16,
  },
  button: { backgroundColor: "#1287B1", padding: 15, borderRadius: 10, marginTop: 4 },
  buttonDisabled: { opacity: 0.6 },
  buttonText: { color: "#fff", textAlign: "center", fontWeight: "800", fontSize: 16 },
  resultBox: {
    marginTop: 20,
    backgroundColor: "#ecfeff",
    borderColor: "#67e8f9",
    borderWidth: 1,
    borderRadius: 10,
    padding: 14,
  },
  resultTitle: { fontWeight: "800", color: "#155e75", marginBottom: 6 },
  resultText: { color: "#164e63", marginBottom: 4 },
});