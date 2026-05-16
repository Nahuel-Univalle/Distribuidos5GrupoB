import { useEffect, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Alert,
} from "react-native";
import * as Location from "expo-location";
import MapView, { Marker } from "react-native-maps";
import { useAuthStore } from "../store/auth";

type MedidorCampus = {
  id: string;
  mac: string;
  lat: number;
  lon: number;
  label: string;
};

type MedidorCercano = MedidorCampus & {
  dist: number;
};

const MEDIDORES_CAMPUS: MedidorCampus[] = [
  {
    id: "univalle-01",
    mac: "AA:BB:CC:01:01",
    lat: -17.39068,
    lon: -66.1524,
    label: "Univalle Pabellón A",
  },
  {
    id: "univalle-02",
    mac: "AA:BB:CC:01:02",
    lat: -17.3912,
    lon: -66.1518,
    label: "Univalle Pabellón B",
  },
  {
    id: "univalle-03",
    mac: "AA:BB:CC:01:03",
    lat: -17.3901,
    lon: -66.153,
    label: "Univalle Biblioteca",
  },
  {
    id: "univalle-04",
    mac: "AA:BB:CC:01:04",
    lat: -17.3896,
    lon: -66.1515,
    label: "Univalle Comedor",
  },
  {
    id: "univalle-05",
    mac: "AA:BB:CC:01:05",
    lat: -17.3918,
    lon: -66.1528,
    label: "Univalle Auditorio",
  },
];

function haversine(a: [number, number], b: [number, number]) {
  const R = 6371000;
  const toRad = (x: number) => (x * Math.PI) / 180;
  const dLat = toRad(b[0] - a[0]);
  const dLon = toRad(b[1] - a[1]);
  const lat1 = toRad(a[0]);
  const lat2 = toRad(b[0]);

  const s =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLon / 2) ** 2;

  return 2 * R * Math.asin(Math.sqrt(s));
}

export default function HomeScreen({ navigation }: any) {
  const { nombre, rol, logout } = useAuthStore();
  const [pos, setPos] = useState<{ lat: number; lon: number } | null>(null);
  const [cercanos, setCercanos] = useState<MedidorCercano[]>([]);

  useEffect(() => {
    async function cargarUbicacion() {
      const { status } = await Location.requestForegroundPermissionsAsync();

      if (status !== "granted") {
        Alert.alert(
          "Permiso denegado",
          "No se podrá identificar medidores cercanos"
        );
        return;
      }

      const loc = await Location.getCurrentPositionAsync({});
      const actual = {
        lat: loc.coords.latitude,
        lon: loc.coords.longitude,
      };

      setPos(actual);

      const sorted: MedidorCercano[] = MEDIDORES_CAMPUS.map((m) => ({
        ...m,
        dist: haversine([actual.lat, actual.lon], [m.lat, m.lon]),
      }))
        .sort((a, b) => a.dist - b.dist)
        .slice(0, 5);

      setCercanos(sorted);
    }

    cargarUbicacion();
  }, []);

  return (
    <ScrollView style={styles.c}>
      <View style={styles.header}>
        <Text style={styles.welcome}>Hola, {nombre}</Text>
        <Text style={styles.rol}>{rol}</Text>
      </View>

      <View style={styles.mapContainer}>
        {pos ? (
          <MapView
            style={styles.map}
            initialRegion={{
              latitude: pos.lat,
              longitude: pos.lon,
              latitudeDelta: 0.01,
              longitudeDelta: 0.01,
            }}
          >
            <Marker
              coordinate={{ latitude: pos.lat, longitude: pos.lon }}
              title="Mi ubicación"
              pinColor="blue"
            />

            {MEDIDORES_CAMPUS.map((m) => (
              <Marker
                key={m.id}
                coordinate={{ latitude: m.lat, longitude: m.lon }}
                title={m.label}
                description={m.mac}
              />
            ))}
          </MapView>
        ) : (
          <View style={styles.loadingBox}>
            <Text style={styles.loadingText}>Obteniendo ubicación...</Text>
          </View>
        )}
      </View>

      <Text style={styles.subtitle}>Medidores cercanos:</Text>

      {cercanos.map((m) => (
        <TouchableOpacity
          key={m.id}
          style={styles.row}
          onPress={() => navigation.navigate("Lectura", { medidor: m })}
        >
          <View>
            <Text style={styles.macText}>{m.label}</Text>
            <Text style={styles.secondaryText}>{m.mac}</Text>
          </View>

          <Text style={styles.dist}>{Math.round(m.dist)} m</Text>
        </TouchableOpacity>
      ))}

      <View style={styles.actions}>
        <TouchableOpacity
          style={[styles.btnSec, styles.actionButton]}
          onPress={() => navigation.navigate("Historial")}
        >
          <Text style={styles.btnText}>Historial</Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.btnSec, styles.actionButton, styles.logoutButton]}
          onPress={() => logout()}
        >
          <Text style={styles.btnText}>Salir</Text>
        </TouchableOpacity>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  c: {
    flex: 1,
    backgroundColor: "#f8fafc",
  },
  header: {
    padding: 16,
  },
  welcome: {
    fontSize: 18,
    fontWeight: "700",
  },
  rol: {
    color: "#64748b",
    marginTop: 4,
  },
  mapContainer: {
    height: 280,
    margin: 12,
    borderRadius: 8,
    overflow: "hidden",
    backgroundColor: "#e2e8f0",
  },
  map: {
    flex: 1,
  },
  loadingBox: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
  },
  loadingText: {
    color: "#475569",
    fontWeight: "600",
  },
  subtitle: {
    fontSize: 14,
    fontWeight: "700",
    margin: 12,
  },
  row: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    backgroundColor: "#fff",
    padding: 12,
    marginHorizontal: 12,
    marginBottom: 6,
    borderRadius: 8,
    borderColor: "#e2e8f0",
    borderWidth: 1,
  },
  macText: {
    fontWeight: "600",
  },
  secondaryText: {
    color: "#64748b",
  },
  dist: {
    color: "#0d6efd",
    fontWeight: "700",
  },
  actions: {
    flexDirection: "row",
    marginTop: 12,
    marginHorizontal: 12,
    marginBottom: 20,
  },
  btnSec: {
    backgroundColor: "#1287B1",
    padding: 12,
    borderRadius: 8,
    alignItems: "center",
  },
  actionButton: {
    flex: 1,
    marginHorizontal: 4,
  },
  logoutButton: {
    backgroundColor: "#94a3b8",
  },
  btnText: {
    color: "#fff",
    fontWeight: "700",
  },
});