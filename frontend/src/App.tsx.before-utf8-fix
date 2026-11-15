import { getRecommendations, type RecommendationRun, type CropRecommendation, type CropVariableCheck } from './services/recommendations';
import React, { useState, useEffect, useMemo, useRef } from 'react';
import {
  Home,
  Activity,
  Sprout,
  Cpu,
  ClipboardCheck,
  Play,
  Square,
  Pause,
  Settings,
  CheckCircle2,
  AlertTriangle,
  ChevronDown,
  ChevronUp,
  LogOut,
  MessageSquare,
  X,
  Send,
  Bot,
  User,
  Loader2,
  Sparkles,
  Thermometer,
  Droplets,
  FlaskConical,
  CloudRain,
  ShieldCheck,
  Radio,
  Wifi,
  Bluetooth,
  Clock,
  Search,
  List,
} from 'lucide-react';
import { login } from './services/auth';
import { getParcels, type Parcel } from './services/parcels';
import {
  getClimateHistory,
  getClimateSummary,
  getSoilPhEstimate,
  type SoilPhEstimate,
  type ClimateDay,
  type ParcelClimateSummary,
} from './services/climate';
// ============================================================
// VALIDACION CENTRALIZADA DE PROCEDENCIA Y ELEGIBILIDAD
// ============================================================

const INVALID_MEASUREMENT_ORIGINS = new Set([
  'simulado',
  'dataset_estimado',
  'demo_simulation',
]);

function isVerifiedMeasurement(
  check: CropVariableCheck | undefined
): boolean {
  if (
    !check ||
    check.measured == null ||
    check.status === 'not_evaluated' ||
    check.is_simulated !== false
  ) {
    return false;
  }

  const origin = check.origin?.trim().toLowerCase();

  if (!origin || INVALID_MEASUREMENT_ORIGINS.has(origin)) {
    return false;
  }

  return true;
}

function isVerifiedEvaluation(
  crop: CropRecommendation | undefined
): boolean {
  if (
    !crop ||
    crop.evaluation_status !== 'complete' ||
    crop.recommendation_eligible !== true ||
    !Array.isArray(crop.checks) ||
    crop.checks.length !== 4
  ) {
    return false;
  }

  const requiredVariables = [
    'soil_temperature',
    'soil_moisture',
    'soil_ph',
    'rainfall',
  ];

  return requiredVariables.every((variable) => {
    const matches = crop.checks.filter(
      (check) => check.variable === variable
    );

    return (
      matches.length === 1 &&
      isVerifiedMeasurement(matches[0])
    );
  });
}


// ============================================================================
// 1. TIPOS DEL ESQUEMA POSTGRESQL v3.3 (agrostake_v3_3_completo.sql)
// ============================================================================
export type UserRole = 'owner' | 'agronomist' | 'viewer';
export type TransportKind = 'ble' | 'wifi_mqtt';
export type ViabilityClass = 'recomendado' | 'condicionado' | 'no_recomendado';
export type VariableCode = 'soil_temperature' | 'soil_moisture' | 'soil_ph' | 'rainfall';
export type CheckStatus = 'in_range' | 'below' | 'above' | 'not_evaluated';
export type SoilTextureCode = 'sand' | 'loamy_sand' | 'sandy_loam' | 'loam' | 'silt_loam' | 'clay';

interface AuthUser {
  id: string;
  org_id: string;
  org_name: string;
  email: string;
  full_name: string;
  phone: string;
  role: UserRole;
}

interface SoilWaterCharacteristic {
  texture_code: SoilTextureCode;
  name_es: string;
  fc_min: number;
  fc_max: number;
  wp_min: number;
  wp_max: number;
}

interface CropSeed {
  id: number;
  common_name_es: string;
  scientific_name: string;
  dataset_label: string | null;
  category: string;
  cycle_days_min: number;
  cycle_days_max: number;
  harvest_notes: string;
  depletion_fraction_p: number;
  root_depth_m_min: number;
  root_depth_m_max: number;
  temp_min: number;
  temp_max: number;
  ph_min: number;
  ph_max: number;
  rain_min: number;
  rain_max: number;
}

interface TelemetryPoint {
  timeLabel: string;
  measured_at: string;
  transport: TransportKind;
  soil_temperature_c: number;
  soil_moisture_pct: number;
  soil_ph: number;
  precip_total_mm: number;
  battery_v: number;
}

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
}

// ============================================================================
// 2. CATÃLOGOS FAO-56, CULTIVOS DEMO Y REGLAS ADVICE_RULES DEL SQL v3.3
// ============================================================================
const SOIL_TEXTURES: Record<SoilTextureCode, SoilWaterCharacteristic> = {
  sand: { texture_code: 'sand', name_es: 'Arena', fc_min: 0.07, fc_max: 0.17, wp_min: 0.02, wp_max: 0.07 },
  loamy_sand: { texture_code: 'loamy_sand', name_es: 'Arena franca', fc_min: 0.11, fc_max: 0.19, wp_min: 0.03, wp_max: 0.10 },
  sandy_loam: { texture_code: 'sandy_loam', name_es: 'Franco arenoso', fc_min: 0.18, fc_max: 0.28, wp_min: 0.06, wp_max: 0.16 },
  loam: { texture_code: 'loam', name_es: 'Franco (EstÃ¡ndar)', fc_min: 0.20, fc_max: 0.30, wp_min: 0.07, wp_max: 0.17 },
  silt_loam: { texture_code: 'silt_loam', name_es: 'Franco limoso', fc_min: 0.22, fc_max: 0.36, wp_min: 0.09, wp_max: 0.21 },
  clay: { texture_code: 'clay', name_es: 'Arcilla', fc_min: 0.32, fc_max: 0.40, wp_min: 0.20, wp_max: 0.24 },
};

function computeFao56MoistureRange(depletionP: number, textureCode: SoilTextureCode): { minPct: number; maxPct: number } {
  const w = SOIL_TEXTURES[textureCode] || SOIL_TEXTURES.loam;
  const fc = (w.fc_min + w.fc_max) / 2;
  const wp = (w.wp_min + w.wp_max) / 2;
  const optimalMinPct = Number(((fc - depletionP * (fc - wp)) * 100).toFixed(1));
  const optimalMaxPct = Number((fc * 100).toFixed(1));
  return { minPct: optimalMinPct, maxPct: optimalMaxPct };
}

const DB_CROPS: CropSeed[] = [
  {
    id: 1,
    common_name_es: 'MaÃ­z',
    scientific_name: 'Zea mays',
    dataset_label: 'maize',
    category: 'Cereal',
    cycle_days_min: 100,
    cycle_days_max: 140,
    harvest_notes: 'Cosecha con grano en madurez fisiolÃ³gica.',
    depletion_fraction_p: 0.55,
    root_depth_m_min: 1.0,
    root_depth_m_max: 1.7,
    temp_min: 18.0,
    temp_max: 30.0,
    ph_min: 5.8,
    ph_max: 7.0,
    rain_min: 50.0,
    rain_max: 120.0,
  },
  {
    id: 2,
    common_name_es: 'Frijol',
    scientific_name: 'Phaseolus vulgaris',
    dataset_label: 'kidneybeans',
    category: 'Leguminosa',
    cycle_days_min: 70,
    cycle_days_max: 110,
    harvest_notes: 'Cosechar con vainas secas.',
    depletion_fraction_p: 0.45,
    root_depth_m_min: 0.5,
    root_depth_m_max: 0.7,
    temp_min: 15.0,
    temp_max: 27.0,
    ph_min: 6.0,
    ph_max: 7.0,
    rain_min: 40.0,
    rain_max: 100.0,
  },
  {
    id: 3,
    common_name_es: 'Tomate',
    scientific_name: 'Solanum lycopersicum',
    dataset_label: 'tomato',
    category: 'Hortaliza',
    cycle_days_min: 90,
    cycle_days_max: 140,
    harvest_notes: 'Cosecha escalonada.',
    depletion_fraction_p: 0.40,
    root_depth_m_min: 0.7,
    root_depth_m_max: 1.5,
    temp_min: 18.0,
    temp_max: 28.0,
    ph_min: 6.0,
    ph_max: 6.8,
    rain_min: 50.0,
    rain_max: 110.0,
  },
  {
    id: 4,
    common_name_es: 'Sorgo',
    scientific_name: 'Sorghum bicolor',
    dataset_label: 'sorghum',
    category: 'Cereal',
    cycle_days_min: 100,
    cycle_days_max: 130,
    harvest_notes: 'Tolerante a sequÃ­a.',
    depletion_fraction_p: 0.55,
    root_depth_m_min: 1.0,
    root_depth_m_max: 2.0,
    temp_min: 20.0,
    temp_max: 32.0,
    ph_min: 5.5,
    ph_max: 7.5,
    rain_min: 40.0,
    rain_max: 100.0,
  },
  {
    id: 5,
    common_name_es: 'Trigo',
    scientific_name: 'Triticum aestivum',
    dataset_label: 'wheat',
    category: 'Cereal',
    cycle_days_min: 110,
    cycle_days_max: 150,
    harvest_notes: 'Cultivo de clima templado/frÃ­o.',
    depletion_fraction_p: 0.55,
    root_depth_m_min: 1.5,
    root_depth_m_max: 1.8,
    temp_min: 10.0,
    temp_max: 24.0,
    ph_min: 6.0,
    ph_max: 7.5,
    rain_min: 40.0,
    rain_max: 90.0,
  },
  {
    id: 6,
    common_name_es: 'Arroz',
    scientific_name: 'Oryza sativa',
    dataset_label: 'rice',
    category: 'Cereal',
    cycle_days_min: 105,
    cycle_days_max: 150,
    harvest_notes: 'Requiere lÃ¡mina de agua; sensible a sequÃ­a.',
    depletion_fraction_p: 0.20,
    root_depth_m_min: 0.5,
    root_depth_m_max: 1.0,
    temp_min: 20.0,
    temp_max: 32.0,
    ph_min: 5.5,
    ph_max: 7.0,
    rain_min: 120.0,
    rain_max: 300.0,
  },
];

function formatAdviceRule(variable: VariableCode, status: 'below' | 'above', current: number, target: number): string {
  const c = current.toFixed(1);
  const t = target.toFixed(1);
  if (variable === 'soil_moisture' && status === 'below') {
    return `Humedad del suelo baja (${c}%): regar para subir hasta ${t}%.`;
  }
  if (variable === 'soil_moisture' && status === 'above') {
    return `Humedad del suelo alta (${c}%): suspender el riego y revisar el drenaje hasta bajar a ${t}%.`;
  }
  if (variable === 'soil_temperature' && status === 'below') {
    return `Temperatura del suelo baja (${c} Â°C): conviene retrasar la siembra o usar acolchado para acercarse a ${t} Â°C.`;
  }
  if (variable === 'soil_temperature' && status === 'above') {
    return `Temperatura del suelo alta (${c} Â°C): conviene usar acolchado y riegos ligeros para bajar hacia ${t} Â°C.`;
  }
  if (variable === 'soil_ph' && status === 'below') {
    return `pH del suelo bajo, suelo Ã¡cido (${current.toFixed(2)}): considerar encalado agrÃ­cola para subir hacia ${target.toFixed(1)}.`;
  }
  if (variable === 'soil_ph' && status === 'above') {
    return `pH del suelo alto, suelo alcalino (${current.toFixed(2)}): considerar materia orgÃ¡nica o azufre elemental para bajar hacia ${target.toFixed(1)}.`;
  }
  if (variable === 'rainfall' && status === 'below') {
    return `Lluvia acumulada baja (${c} mm): programar riego complementario para aproximarse a ${t} mm.`;
  }
  return `Lluvia acumulada alta (${c} mm): vigilar encharcamiento y mejorar el drenaje; el objetivo es cerca de ${t} mm.`;
}

function calcSoftVariableScore(val: number, min: number, max: number, tolerance: number): number {
  if (val >= min && val <= max) return 100;
  const dist = val < min ? min - val : val - max;
  return Math.max(0, Math.round((1 - dist / tolerance) * 100));
}

function formatSeconds(sec: number): string {
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

// ============================================================================
// 3. COMPONENTE MINIATURA DE BATERÃA
// ============================================================================
const MinimalBatteryStatus: React.FC<{ batteryV: number }> = ({ batteryV }) => {
  const pct = Math.min(100, Math.max(5, Math.round(((batteryV - 3.3) / (4.2 - 3.3)) * 100)));
  const barColor = pct > 35 ? '#159447' : pct > 15 ? '#E9A11B' : '#E34545';

  return (
    <div
      className="inline-flex items-center gap-2 bg-[#F8F8F8] border border-[#D5D5D5] px-2.5 py-1.5 rounded-lg"
      title={`BaterÃ­a simulada (demo): ${pct}% (${batteryV.toFixed(2)} V). Sin mediciÃ³n fÃ­sica confirmada.`}
    >
      <div className="relative w-6 h-3.5 border-[1.5px] border-[#202020] rounded-[3px] p-[1.5px] flex items-center">
        <div
          className="h-full rounded-[1px] transition-all duration-300"
          style={{ width: `${pct}%`, backgroundColor: barColor }}
        />
        <div className="w-[2px] h-1.5 bg-[#202020] rounded-r-sm absolute -right-[3.5px] top-1/2 -translate-y-1/2" />
      </div>
      <span className="text-xs font-bold text-[#202020] tabular-nums">{pct}%</span>
    </div>
  );
};

// ============================================================================
// 4. ILUSTRACIÃ“N LIMPIA DE LA ESTACA (SOPORTE PARA image_015581.jpg)
// ============================================================================
void MinimalBatteryStatus;

const StakePhotoDisplay: React.FC = () => {
  const [imgError, setImgError] = useState(false);

  return (
    <div className="relative w-full h-64 md:h-72 bg-[#F8F8F8] border border-[#DEDEDE] rounded-2xl overflow-hidden flex items-center justify-center p-4">
      {!imgError ? (
        <img
          src="/image_015581.jpg"
          alt="Estaca AgroStake"
          onError={() => setImgError(true)}
          className="w-full h-full object-contain rounded-xl"
        />
      ) : (
        <svg viewBox="0 0 260 320" className="w-44 h-60">
          <defs>
            <linearGradient id="pvcBody" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="#E5E4DF" />
              <stop offset="45%" stopColor="#FAF9F5" />
              <stop offset="100%" stopColor="#CFCBC2" />
            </linearGradient>
            <linearGradient id="inoxRod" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="#7A8288" />
              <stop offset="50%" stopColor="#E1E6EB" />
              <stop offset="100%" stopColor="#52585D" />
            </linearGradient>
          </defs>
          <ellipse cx="130" cy="296" rx="54" ry="10" fill="rgba(0,0,0,0.10)" />
          <rect x="103" y="195" width="6" height="92" rx="3" fill="url(#inoxRod)" />
          <rect x="127" y="202" width="6" height="96" rx="3" fill="url(#inoxRod)" />
          <rect x="151" y="195" width="6" height="92" rx="3" fill="url(#inoxRod)" />
          <rect x="86" y="34" width="88" height="168" rx="6" fill="url(#pvcBody)" stroke="#C4C0B6" strokeWidth="1.5" />
          <rect x="82" y="28" width="96" height="44" rx="5" fill="url(#pvcBody)" stroke="#B8B4AA" strokeWidth="1.5" />
          <rect x="82" y="154" width="96" height="48" rx="5" fill="url(#pvcBody)" stroke="#B8B4AA" strokeWidth="1.5" />
          <rect x="78" y="24" width="104" height="7" rx="3.5" fill="#D8D5CD" stroke="#B0ACA2" strokeWidth="1" />
        </svg>
      )}
    </div>
  );
};

// ============================================================================
// 5. BURBUJA DE CHAT FLOTANTE ESTILO MESSENGER (ESQUINA INFERIOR DERECHA)
// ============================================================================
const AgroAssistantBubble: React.FC<{
  latest: TelemetryPoint;
  texture: SoilTextureCode;
}> = ({ latest, texture }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'init-1',
      role: 'assistant',
      content:
        'Hola. Soy el asistente agrÃ­cola de AgroStake. Estoy conectado a los datos actuales de tu parcela. Â¿Tienes dudas sobre quÃ© sembrar, cÃ³mo regar o quÃ© significan tus mÃ©tricas?',
      timestamp: new Date().toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit' }),
    },
  ]);

  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (isOpen) {
      endRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, isOpen]);

  const generateSmartAnswer = (question: string): string => {
    const q = question.toLowerCase();

    // ProtecciÃ³n: no emitir recomendaciones agrÃ­colas con telemetrÃ­a simulada.
    if (
      q.includes('sembrar') ||
      q.includes('cultiv') ||
      q.includes('planta') ||
      q.includes('recomienda') ||
      q.includes('humedad') ||
      q.includes('regar') ||
      q.includes('riego') ||
      q.includes('agua')
    ) {
      return 'No puedo determinar quÃ© cultivo sembrar ni si necesitas regar utilizando las lecturas actuales. La temperatura, la humedad del suelo, el pH y la lluvia de este simulador son demostrativos. Para una evaluaciÃ³n real necesitamos mediciones fÃ­sicas verificadas y datos climÃ¡ticos de NASA POWER asociados a tu parcela.';
    }
    const evaluated = DB_CROPS.map((crop) => {
      const moistRange = computeFao56MoistureRange(crop.depletion_fraction_p, texture);
      const tOk = latest.soil_temperature_c >= crop.temp_min && latest.soil_temperature_c <= crop.temp_max;
      const mOk = latest.soil_moisture_pct >= moistRange.minPct && latest.soil_moisture_pct <= moistRange.maxPct;
      const pOk = latest.soil_ph >= crop.ph_min && latest.soil_ph <= crop.ph_max;
      const rOk = latest.precip_total_mm >= crop.rain_min && latest.precip_total_mm <= crop.rain_max;
      const okCount = [tOk, mOk, pOk, rOk].filter(Boolean).length;
      return { crop, okCount, moistRange };
    }).sort((a, b) => b.okCount - a.okCount);

    if (q.includes('sembrar') || q.includes('cultiv') || q.includes('planta') || q.includes('recomienda')) {
      const best = evaluated.filter((e) => e.okCount >= 3).map((e) => `${e.crop.common_name_es} (${e.okCount}/4)`);
      if (best.length > 0) {
        return `Con ${latest.soil_temperature_c.toFixed(1)} Â°C, ${latest.soil_moisture_pct.toFixed(1)}% de humedad, pH simulado ${latest.soil_ph.toFixed(2)} y ${latest.precip_total_mm.toFixed(1)} mm de lluvia, los cultivos mÃ¡s aptos son: ${best.join(', ')}.`;
      }
      return `El cultivo mÃ¡s cercano es ${evaluated[0].crop.common_name_es} (${evaluated[0].okCount}/4 condiciones). Revisa el apartado de Recomendaciones para ajustar la humedad antes de sembrar.`;
    }

    if (q.includes('humedad') || q.includes('regar') || q.includes('riego') || q.includes('agua')) {
      const refRange = computeFao56MoistureRange(0.5, texture);
      if (latest.soil_moisture_pct < refRange.minPct) {
        return formatAdviceRule('soil_moisture', 'below', latest.soil_moisture_pct, refRange.minPct);
      }
      if (latest.soil_moisture_pct > refRange.maxPct) {
        return formatAdviceRule('soil_moisture', 'above', latest.soil_moisture_pct, refRange.maxPct);
      }
      return `La humedad actual es de ${latest.soil_moisture_pct.toFixed(1)}%, dentro del rango Ã³ptimo (${refRange.minPct}%â€“${refRange.maxPct}%) para suelo ${SOIL_TEXTURES[texture].name_es}.`;
    }

    if (q.includes('ph') || q.includes('acidez') || q.includes('cal')) {
      if (latest.soil_ph < 5.8) {
        return formatAdviceRule('soil_ph', 'below', latest.soil_ph, 6.2);
      }
      if (latest.soil_ph > 7.2) {
        return formatAdviceRule('soil_ph', 'above', latest.soil_ph, 6.8);
      }
      return `El pH simulado estÃ¡ en ${latest.soil_ph.toFixed(2)}, nivel adecuado para la absorciÃ³n de nutrientes en la raÃ­z.`;
    }

    if (q.includes('temperatura') || q.includes('calor') || q.includes('frio')) {
      return `La temperatura del suelo es de ${latest.soil_temperature_c.toFixed(1)} Â°C. El rango ideal para la mayorÃ­a de los cultivos del catÃ¡logo estÃ¡ entre 18 Â°C y 30 Â°C.`;
    }

    return `Resumen de datos disponibles (${latest.transport === 'wifi_mqtt' ? 'Wi-Fi MQTT' : 'Bluetooth BLE'}): Temperatura ${latest.soil_temperature_c.toFixed(1)} Â°C, Humedad ${latest.soil_moisture_pct.toFixed(1)}%, pH simulado ${latest.soil_ph.toFixed(2)} y lluvia simulada ${latest.precip_total_mm.toFixed(1)} mm. Estos valores son demostrativos y no deben utilizarse para tomar decisiones agrÃ­colas reales.`;
  };

  const sendMessage = async (textOverride?: string) => {
    const cleanText = (textOverride ?? input).trim();
    if (!cleanText || isTyping) return;

    const userMessage: ChatMessage = {
      id: `u-${Date.now()}`,
      role: 'user',
      content: cleanText,
      timestamp: new Date().toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setIsTyping(true);

    try {
      const ctrl = new AbortController();
      const timer = setTimeout(() => ctrl.abort(), 2500);
      const res = await fetch('http://localhost:8000/api/agent/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: `[CONTEXTO DE DATOS: Los valores de temperatura, humedad, pH y precipitaciÃ³n enviados en esta solicitud son SIMULADOS. No provienen de sensores fÃ­sicos ni deben interpretarse como mediciones reales. No recomiendes acciones agrÃ­colas reales basadas en estos valores. Si el usuario pregunta por condiciones reales, indica que faltan mediciones fÃ­sicas verificadas. Esta nota describe la procedencia de los datos, no sustituye la pregunta del usuario.] ${cleanText}`,
          soil_temperature_c: latest.soil_temperature_c,
          soil_moisture_pct: latest.soil_moisture_pct,
          soil_ph: latest.soil_ph,
          precip_total_mm: latest.precip_total_mm,
          soil_texture: texture,
          transport: latest.transport,
        }),
        signal: ctrl.signal,
      });
      clearTimeout(timer);

      if (!res.ok) throw new Error('Backend local no activo');
      const data = await res.json();
      setMessages((prev) => [
        ...prev,
        {
          id: `b-${Date.now()}`,
          role: 'assistant',
          content: data.reply || data.message || generateSmartAnswer(cleanText),
          timestamp: new Date().toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit' }),
        },
      ]);
    } catch {
      await new Promise((r) => setTimeout(r, 400));
      setMessages((prev) => [
        ...prev,
        {
          id: `b-${Date.now()}`,
          role: 'assistant',
          content: generateSmartAnswer(cleanText),
          timestamp: new Date().toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit' }),
        },
      ]);
    } finally {
      setIsTyping(false);
    }
  };

  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col items-end">
      {isOpen && (
        <div className="mb-3.5 w-[360px] max-w-[calc(100vw-2rem)] bg-white border border-[#D5D5D5] rounded-2xl shadow-2xl overflow-hidden flex flex-col">
          <div className="bg-[#1E1E1E] text-white px-4 py-3 flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg bg-[#F39200] text-[#1E1E1E] flex items-center justify-center">
                <Bot className="w-4 h-4 stroke-[2.2]" />
              </div>
              <div>
                <h4 className="text-xs font-bold tracking-tight">Asistente AgrÃ­cola IA</h4>
                <span className="text-[11px] text-neutral-400 block">Sincronizado con PostgreSQL v3.3</span>
              </div>
            </div>
            <button
              onClick={() => setIsOpen(false)}
              className="w-7 h-7 rounded-lg bg-neutral-800 hover:bg-neutral-700 flex items-center justify-center text-neutral-300 cursor-pointer"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          <div className="bg-[#F8F8F8] border-b border-[#E5E5E5] px-3 py-1.5 flex justify-between text-[11px] text-[#555555]">
            <span>Temp: <strong className="text-[#202020]">{latest.soil_temperature_c.toFixed(1)}Â°C</strong></span>
            <span>Hum: <strong className="text-[#202020]">{latest.soil_moisture_pct.toFixed(1)}%</strong></span>
            <span>pH (Sim): <strong className="text-[#202020]">{latest.soil_ph.toFixed(2)}</strong></span>
            <span>Lluvia: <strong className="text-[#202020]">{latest.precip_total_mm.toFixed(0)}mm</strong></span>
          </div>

          <div className="h-72 overflow-y-auto p-3.5 space-y-2.5 bg-[#EEEEEE]/50">
            {messages.map((m) => (
              <div key={m.id} className={`flex items-end gap-2 ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                {m.role === 'assistant' && (
                  <div className="w-6 h-6 rounded-md bg-[#1E1E1E] text-[#F39200] flex items-center justify-center shrink-0">
                    <Sparkles className="w-3.5 h-3.5" />
                  </div>
                )}
                <div
                  className={`max-w-[78%] rounded-2xl px-3 py-2 text-xs leading-relaxed ${
                    m.role === 'user'
                      ? 'bg-[#1E1E1E] text-white rounded-br-sm'
                      : 'bg-white text-[#202020] border border-[#DEDEDE] rounded-bl-sm shadow-sm'
                  }`}
                >
                  <p>{m.content}</p>
                  <span className="block text-[10px] opacity-60 text-right mt-1">{m.timestamp}</span>
                </div>
                {m.role === 'user' && (
                  <div className="w-6 h-6 rounded-md bg-[#DEDEDE] text-[#202020] flex items-center justify-center shrink-0">
                    <User className="w-3.5 h-3.5" />
                  </div>
                )}
              </div>
            ))}
            {isTyping && (
              <div className="flex items-center gap-2 text-xs text-[#777777] bg-white border border-[#DEDEDE] rounded-xl px-3 py-1.5 w-fit">
                <Loader2 className="w-3.5 h-3.5 animate-spin text-[#F39200]" />
                <span>Analizando consulta...</span>
              </div>
            )}
            <div ref={endRef} />
          </div>

          <div className="px-3 py-1.5 bg-white border-t border-[#EEEEEE] flex gap-1.5 overflow-x-auto">
            {['Â¿QuÃ© puedo sembrar?', 'Â¿Necesito regar?', 'Estado del pH'].map((q) => (
              <button
                key={q}
                type="button"
                onClick={() => sendMessage(q)}
                className="shrink-0 text-[11px] bg-[#F4F4F4] hover:bg-[#1E1E1E] hover:text-white text-[#202020] px-2.5 py-1 rounded-md border border-[#DEDEDE] transition-colors cursor-pointer"
              >
                {q}
              </button>
            ))}
          </div>

          <form
            onSubmit={(e) => {
              e.preventDefault();
              sendMessage();
            }}
            className="p-2.5 bg-white border-t border-[#D5D5D5] flex gap-2"
          >
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Pregunta sobre tus cultivos o widgets..."
              className="flex-1 bg-[#F8F8F8] border border-[#D5D5D5] rounded-xl px-3 py-2 text-xs text-[#202020] focus:outline-none focus:border-[#1E1E1E]"
            />
            <button
              type="submit"
              disabled={!input.trim() || isTyping}
              className="w-9 h-9 rounded-xl bg-[#F39200] hover:bg-[#e08600] disabled:opacity-40 text-[#1E1E1E] flex items-center justify-center transition-colors cursor-pointer"
            >
              <Send className="w-4 h-4" />
            </button>
          </form>
        </div>
      )}

      <button
        onClick={() => setIsOpen((o) => !o)}
        className="flex items-center gap-2.5 h-12 px-4 rounded-full bg-[#1E1E1E] hover:bg-black text-white shadow-lg border border-[#333333] transition-all cursor-pointer"
      >
        <div className="w-7 h-7 rounded-full bg-[#F39200] text-[#1E1E1E] flex items-center justify-center">
          {isOpen ? <X className="w-4 h-4 stroke-[2.4]" /> : <MessageSquare className="w-4 h-4 stroke-[2.2]" />}
        </div>
        <span className="text-xs font-semibold pr-1">{isOpen ? 'Cerrar asistente' : 'Preguntar a la IA'}</span>
      </button>
    </div>
  );
};

// ============================================================================
// 6. APLICACIÃ“N PRINCIPAL AGROSTAKE
// ============================================================================
export function App() {
  // --- AutenticaciÃ³n y Registro ---
  const [user, setUser] = useState<AuthUser | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [parcels, setParcels] = useState<Parcel[]>([]);
  const [isLoadingParcels, setIsLoadingParcels] = useState(false);
  const [parcelError, setParcelError] = useState('');
  const [climateHistory, setClimateHistory] = useState<ClimateDay[]>([]);
  const [climateSummary, setClimateSummary] = useState<ParcelClimateSummary | null>(null);
  const [climateLoading, setClimateLoading] = useState(false);
  const [climateError, setClimateError] = useState('');
  const [soilPh, setSoilPh] = useState<SoilPhEstimate | null>(null);
  const [recommendationRun, setRecommendationRun] = useState<RecommendationRun | null>(null);
  const [recommendationsLoading, setRecommendationsLoading] = useState(false);
  const [recommendationsError, setRecommendationsError] = useState('');
  const [authMode, setAuthMode] = useState<'login' | 'register'>('login');
  const [loginEmail, setLoginEmail] = useState('');
  const [loginPass, setLoginPass] = useState('');
  const [authError, setAuthError] = useState('');

  const [regFirstName, setRegFirstName] = useState('');
  const [regLastName, setRegLastName] = useState('');
  const [regEmail, setRegEmail] = useState('');
  const [regPhone, setRegPhone] = useState('');
  const [regPassword, setRegPassword] = useState('');
  const [regConfirmPass, setRegConfirmPass] = useState('');

  // --- NavegaciÃ³n ---
  const [activeTab, setActiveTab] = useState<'home' | 'telemetry' | 'crops' | 'sensors' | 'advice'>('home');
  const [expandedCropId, setExpandedCropId] = useState<number | null>(1);
  const [cropSearch, setCropSearch] = useState('');
  const [cropFilterClass, setCropFilterClass] = useState<'all' | ViabilityClass>('all');

  // --- ConexiÃ³n ESP32-C3 (Wi-Fi MQTT / Bluetooth BLE) ---
  const [espTransport, setEspTransport] = useState<TransportKind>('wifi_mqtt');
  const [espConnected, setEspConnected] = useState<boolean>(false);
  const [connectionWarning, setConnectionWarning] = useState<string>('');
  const [telemetryError, setTelemetryError] = useState<string>('');
  const [lastTelemetryAt, setLastTelemetryAt] = useState<string | null>(null);
  const deviceUid = 'ESP32C3-STAKE-001';

  // --- Control de AnÃ¡lisis y Temporizador ---
  const [showDurationModal, setShowDurationModal] = useState<boolean>(false);
  const [selectedDurationSec, setSelectedDurationSec] = useState<number>(300);
  const [isAnalysisActive, setIsAnalysisActive] = useState<boolean>(false);
  const [isBootingAnalysis, setIsBootingAnalysis] = useState<boolean>(false);
  const [analysisStepText, setAnalysisStepText] = useState<string>('');
  const [remainingSec, setRemainingSec] = useState<number | null>(null);
  const [elapsedSec, setElapsedSec] = useState<number>(0);

  // --- Muestreo y Textura FAO-56 ---
  const [sampleIntervalSec, setSampleIntervalSec] = useState<number>(2);
  const [isConfiguringTime, setIsConfiguringTime] = useState<boolean>(false);
  const [soilTexture, setSoilTexture] = useState<SoilTextureCode>('loam');

  // --- Historial de Lecturas ---
  const [history, setHistory] = useState<TelemetryPoint[]>(() => {
    const now = Date.now();
    return Array.from({ length: 12 }, (_, idx) => {
      const t = new Date(now - (11 - idx) * 2000);
      return {
        timeLabel: t.toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
        measured_at: t.toISOString(),
        transport: 'wifi_mqtt',
        soil_temperature_c: Number((22.4 + Math.sin(idx * 0.5) * 0.8).toFixed(1)),
        soil_moisture_pct: Number((21.5 + Math.cos(idx * 0.4) * 1.4).toFixed(1)),
        soil_ph: Number((6.42 + Math.sin(idx * 0.35) * 0.08).toFixed(2)),
        precip_total_mm: Number((69.5 + Math.sin(idx * 0.25) * 1.2).toFixed(1)),
        battery_v: 4.04,
      };
    });
  });

  const latest = history[history.length - 1];

  // Carga las parcelas reales de la organizaciÃ³n usando el JWT del login.
  useEffect(() => {
    if (!accessToken) {
      setParcels([]);
      setParcelError('');
      return;
    }

    let cancelled = false;
    setIsLoadingParcels(true);
    setParcelError('');

    getParcels(accessToken)
      .then((items) => {
        if (!cancelled) setParcels(items);
      })
      .catch((error) => {
        if (!cancelled) {
          setParcelError(
            error instanceof Error
              ? error.message
              : 'No fue posible consultar las parcelas.'
          );
          setParcels([]);
        }
      })
      .finally(() => {
        if (!cancelled) setIsLoadingParcels(false);
      });

    return () => {
      cancelled = true;
    };
  }, [accessToken]);

  // TelemetrÃ­a REAL del ESP32: consulta la estaca y sus lecturas al backend.
  // El firmware publica cada 30 s; consultamos cada 5 s para reflejar la Ãºltima lectura.
  useEffect(() => {
    if (!accessToken) {
      setEspConnected(false);
      setLastTelemetryAt(null);
      setTelemetryError('');
      return;
    }

    let cancelled = false;

    const apiBase = (
      import.meta.env.VITE_BUSINESS_API_URL || 'http://127.0.0.1:8102'
    ).replace(/\/$/, '');

    const loadTelemetry = async () => {
      try {
        const headers = { Authorization: `Bearer ${accessToken}` };
        const stakesResponse = await fetch(`${apiBase}/api/v1/stakes`, { headers });
        if (!stakesResponse.ok) {
          throw new Error(`No se pudieron consultar las estacas (HTTP ${stakesResponse.status}).`);
        }

        const stakesPayload: unknown = await stakesResponse.json();
        const stakes = Array.isArray(stakesPayload) ? stakesPayload : [stakesPayload];
        const stake = stakes.find(
          (item: any) => item?.device_uid === deviceUid
        );

        if (!stake?.id) {
          if (!cancelled) {
            setEspConnected(false);
            setTelemetryError(`No se encontrÃ³ la estaca ${deviceUid} en esta organizaciÃ³n.`);
          }
          return;
        }

        const readingsResponse = await fetch(
          `${apiBase}/api/v1/stakes/${encodeURIComponent(stake.id)}/readings`,
          { headers }
        );
        if (!readingsResponse.ok) {
          throw new Error(`No se pudieron consultar las lecturas (HTTP ${readingsResponse.status}).`);
        }

        const readingsPayload: unknown = await readingsResponse.json();
        const readings = Array.isArray(readingsPayload)
          ? readingsPayload
          : Array.isArray((readingsPayload as any)?.items)
            ? (readingsPayload as any).items
            : [];

        if (cancelled) return;

        const realReadings = readings.filter((r: any) => r?.is_simulated === false);
        const newest = realReadings[0];
        const seenAt = newest?.measured_at ?? stake.last_seen_at ?? null;
        const ageMs = seenAt ? Date.now() - new Date(seenAt).getTime() : Number.POSITIVE_INFINITY;
        const connected = stake.is_active === true &&
          Number.isFinite(ageMs) && ageMs >= -60000 && ageMs <= 90000;

        setEspConnected(connected);
        setEspTransport('wifi_mqtt');
        setLastTelemetryAt(seenAt);
        setTelemetryError(
          realReadings.length === 0
            ? 'La estaca existe, pero todavÃ­a no tiene lecturas fÃ­sicas registradas.'
            : connected
              ? ''
              : 'La Ãºltima lectura tiene mÃ¡s de 90 segundos; revisa el Wi-Fi del ESP32.'
        );

        if (realReadings.length > 0) {
          const chronological = realReadings
            .filter((r: any) =>
              r && typeof r.measured_at === 'string' &&
              r.soil_temperature_c != null &&
              r.soil_moisture_pct != null &&
              Number.isFinite(Number(r.soil_temperature_c)) &&
              Number.isFinite(Number(r.soil_moisture_pct))
            )
            .slice()
            .reverse()
            .slice(-20);

          setHistory((previous) => {
            const fallback = previous[previous.length - 1];
            const points: TelemetryPoint[] = chronological.map((r: any) => {
              const measuredDate = new Date(r.measured_at);
              return {
                timeLabel: Number.isNaN(measuredDate.getTime())
                  ? r.measured_at
                  : measuredDate.toLocaleTimeString('es-MX', {
                      hour: '2-digit', minute: '2-digit', second: '2-digit'
                    }),
                measured_at: r.measured_at,
                transport: r.transport === 'ble' ? 'ble' : 'wifi_mqtt',
                soil_temperature_c: Number(r.soil_temperature_c),
                soil_moisture_pct: Number(r.soil_moisture_pct),
                // El ESP32 actual no mide pH ni lluvia; se conservan como datos externos/demo.
                soil_ph: fallback.soil_ph,
                precip_total_mm: fallback.precip_total_mm,
                battery_v: Number.isFinite(Number(r.battery_v)) ? Number(r.battery_v) : 0,
              };
            });
            return points.length ? points : previous;
          });
        }
      } catch (error) {
        if (!cancelled) {
          setEspConnected(false);
          setTelemetryError(
            error instanceof Error ? error.message : 'Error consultando la telemetrÃ­a del ESP32.'
          );
        }
      }
    };

    loadTelemetry();
    const pollId = window.setInterval(loadTelemetry, 5000);

    return () => {
      cancelled = true;
      window.clearInterval(pollId);
    };
  }, [accessToken]);

  // Datos NASA POWER y pH SoilGrids de la primera parcela.
  useEffect(() => {
    const parcelId = parcels[0]?.id;

    if (!accessToken || !parcelId) {
      setClimateHistory([]);
      setClimateSummary(null);
      setClimateError('');
      setClimateLoading(false);
      setSoilPh(null);
      return;
    }

    let cancelled = false;

    setClimateLoading(true);
    setClimateError('');
    setClimateHistory([]);
    setClimateSummary(null);
    setSoilPh(null);

    Promise.allSettled([
      getClimateHistory(parcelId, accessToken),
      getClimateSummary(parcelId, accessToken),
      getSoilPhEstimate(parcelId, accessToken),
    ]).then(([historyResult, summaryResult, phResult]) => {
      if (cancelled) return;

      if (historyResult.status === 'fulfilled') {
        setClimateHistory(historyResult.value);
      }

      if (summaryResult.status === 'fulfilled') {
        setClimateSummary(summaryResult.value);
      }

      if (phResult.status === 'fulfilled') {
        setSoilPh(phResult.value);
      }

      if (
        historyResult.status === 'rejected' ||
        summaryResult.status === 'rejected'
      ) {
        setClimateError('No se pudieron cargar todos los datos NASA.');
      }
    }).finally(() => {
      if (!cancelled) setClimateLoading(false);
    });

    return () => {
      cancelled = true;
    };
  }, [accessToken, parcels]);
  // Panel temporal de verificacion de datos NASA POWER.
  // Consultar recomendaciones existentes del backend.
  useEffect(() => {
    const parcelId = parcels[0]?.id;

    if (!accessToken || !parcelId) {
      setRecommendationRun(null);
      setRecommendationsError('');
      setRecommendationsLoading(false);
      return;
    }

    let cancelled = false;

    setRecommendationsLoading(true);
    setRecommendationsError('');
    setRecommendationRun(null);

    getRecommendations(parcelId, accessToken)
      .then((data) => {
        if (!cancelled) setRecommendationRun(data);
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setRecommendationsError(
            error instanceof Error
              ? error.message
              : 'No se pudieron cargar las recomendaciones.'
          );
        }
      })
      .finally(() => {
        if (!cancelled) setRecommendationsLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [accessToken, parcels]);

  const backendRecommendationsPanel = (
    <section className="bg-white border border-[#D5D5D5] rounded-2xl p-6 my-4">
      <h3 className="text-sm font-bold text-[#202020] mb-2">
        AnÃ¡lisis agrÃ­cola del backend
      </h3>

      <p className="text-xs text-[#777777] mb-4">
        EvaluaciÃ³n basada en datos disponibles de la parcela.
        Las mediciones del suelo aÃºn estÃ¡n pendientes.
      </p>

      {recommendationsLoading && (
        <p className="text-sm">Cargando recomendaciones...</p>
      )}

      {recommendationsError && (
        <p className="text-sm text-red-600">
          {recommendationsError}
        </p>
      )}

      {!recommendationsLoading && recommendationRun && (
        <div className="space-y-3">
          <p className="text-xs text-[#777777]">
            Fecha de anÃ¡lisis: {recommendationRun.window_end}
          </p>

          {(recommendationRun.results ?? []).map((crop) => {
            const missing = crop.checks.filter(
              (check) => check.status === 'not_evaluated'
            );

            const verifiedEvaluation = isVerifiedEvaluation(crop);

            const rainfall = crop.checks.find(
              (check) => check.variable === 'rainfall'
            );

            return (
              <div
                key={crop.crop_id}
                className="border border-[#E5E5E5] rounded-xl p-3"
              >
                <p className="font-bold text-sm text-[#202020]">
                  {crop.common_name_es}
                </p>

                <p className="text-xs italic text-[#777777]">
                  {crop.scientific_name}
                </p>

                <p className="text-xs font-semibold text-amber-700 mt-2">
                  {verifiedEvaluation
                    ? `ClasificaciÃ³n: ${crop.classification}`
                    : missing.length > 0
                    ? 'EvaluaciÃ³n incompleta: faltan mediciones'
                    : 'EvaluaciÃ³n no verificada: sin recomendaciÃ³n definitiva'}
                </p>

                <p className="text-xs text-[#555555] mt-1">
                  Variables pendientes: {missing.length} de {crop.checks.length}
                </p>

                {rainfall?.measured != null && (
                  <p className="text-xs text-[#159447] mt-1">
                    Lluvia NASA POWER: {rainfall.measured.toFixed(2)} mm
                    {' Â· '}
                    Estado: {rainfall.status}
                  </p>
                )}
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
  const nasaClimatePanel = (
    <section className="rounded-xl border border-green-200 bg-green-50 p-4 my-4">
      <h3 className="font-bold text-green-900">
        NASA POWER - Datos climaticos reales
      </h3>

      {climateLoading && <p>Cargando datos NASA...</p>}

      {climateError && (
        <p className="text-red-600">Error: {climateError}</p>
      )}

      <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-3">
        <p className="text-sm font-semibold text-amber-900">
          pH del suelo
        </p>

        {climateLoading ? (
          <p className="text-sm">Consultando SoilGrids...</p>
        ) : soilPh?.ph != null ? (
          <>
            <p className="text-2xl font-bold text-amber-900">
              {soilPh.ph.toFixed(2)}
            </p>
            <p className="text-xs text-amber-800">
              {soilPh.simulated
                ? 'SIMULACIÃ“N PARA DEMOSTRACIÃ“N - No es una mediciÃ³n real'
                : `EstimaciÃ³n SoilGrids (${soilPh.depth ?? 'profundidad no especificada'})`}
            </p>
          </>
        ) : (
          <p className="text-sm">pH no disponible</p>
        )}
      </div>
      {!climateLoading && climateSummary && (
        <div className="grid grid-cols-2 gap-3 mt-3">
          <div>
            <p className="text-sm">Lluvia acumulada</p>
            <strong>
              {climateSummary.rainfall_30d?.precip_total_mm ?? 'N/D'} mm
            </strong>
          </div>

          <div>
            <p className="text-sm">Dias con datos</p>
            <strong>
              {climateSummary.rainfall_30d?.days_with_data ?? 0}
            </strong>
          </div>

          <div>
            <p className="text-sm">Temperatura ambiental promedio</p>
            <strong>
              {(() => {
                const values = climateHistory
                  .map(day => day.air_temp_c)
                  .filter((value): value is number => value !== null);

                if (values.length === 0) return 'N/D';

                return (
                  values.reduce((sum, value) => sum + value, 0) /
                  values.length
                ).toFixed(2) + ' Â°C';
              })()}
            </strong>
          </div>

          <div>
            <p className="text-sm">Ultima fecha valida</p>
            <strong>
              {climateSummary.rainfall_30d?.last_valid_date ?? 'N/D'}
            </strong>
          </div>
        </div>
      )}
    </section>
  );
  // Temporizador por segundo para detener en automÃ¡tico al cumplir la duraciÃ³n
  useEffect(() => {
    if (!user || !isAnalysisActive || isConfiguringTime || !espConnected) return;

    const secTimer = setInterval(() => {
      setElapsedSec((prev) => prev + 1);
      if (selectedDurationSec > 0) {
        setRemainingSec((prev) => {
          if (prev === null) return selectedDurationSec - 1;
          if (prev <= 1) {
            setIsAnalysisActive(false);
            return 0;
          }
          return prev - 1;
        });
      }
    }, 1000);

    return () => clearInterval(secTimer);
  }, [user, isAnalysisActive, isConfiguringTime, espConnected, selectedDurationSec]);

  // Las muestras del ESP32 llegan desde el backend mediante el polling anterior.
  // No generar Math.random(): temperatura y humedad deben proceder del hardware.

  // --- ValidaciÃ³n de conexiÃ³n antes de abrir el selector de duraciÃ³n ---
  const handleClickInitAnalysisButton = () => {
    if (!espConnected) {
      setConnectionWarning(
        `No hay una lectura reciente de ${deviceUid}. Verifica que el ESP32 estÃ© conectado al Wi-Fi y enviando datos.`
      );
      return;
    }
    setConnectionWarning('');
    setShowDurationModal(true);
  };

  // --- Arrancar anÃ¡lisis con la duraciÃ³n elegida ---
  const handleConfirmDurationAndStart = (durationSec: number) => {
    if (!espConnected) {
      setShowDurationModal(false);
      setConnectionWarning('No hay conexiÃ³n reciente con el ESP32. Revisa el Wi-Fi antes de iniciar el anÃ¡lisis.');
      return;
    }
    setSelectedDurationSec(durationSec);
    setShowDurationModal(false);
    setIsBootingAnalysis(true);

    const steps = [
      `Preparando adquisiciÃ³n de datos reales de ${deviceUid} Â· Transporte seleccionado: ${espTransport === 'wifi_mqtt' ? 'Wi-Fi (MQTT)' : 'Bluetooth (BLE)'}...`,
      'Esperando lecturas reales de temperatura y humedad...',
      'Integrando pH disponible y datos climÃ¡ticos de NASA POWER...',
    ];
    setAnalysisStepText(steps[0]);

    setTimeout(() => setAnalysisStepText(steps[1]), 450);
    setTimeout(() => setAnalysisStepText(steps[2]), 900);
    setTimeout(() => {
      setIsBootingAnalysis(false);
      setAnalysisStepText('');
      setElapsedSec(0);
      setRemainingSec(durationSec > 0 ? durationSec : null);
      setIsAnalysisActive(true);
      setActiveTab('telemetry');
    }, 1350);
  };

  const handleStopAnalysis = () => {
    setIsAnalysisActive(false);
    setRemainingSec(null);
  };

  // --- Login y Registro ---
  const handleLoginSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setAuthError('');

    if (!loginEmail.trim() || !loginPass) {
      setAuthError('Ingresa tu correo y contraseÃ±a.');
      return;
    }

    try {
      const auth = await login(loginEmail.trim(), loginPass);
      const response = await fetch('http://127.0.0.1:8000/api/v1/users/me', {
        headers: { Authorization: `Bearer ${auth.access_token}` },
      });
      if (!response.ok) {
        throw new Error('La sesiÃ³n se iniciÃ³, pero no se pudo consultar el perfil.');
      }
      const profile = await response.json();

      setAccessToken(auth.access_token);
      setUser({
        id: auth.user_id,
        org_id: auth.org_id,
        org_name: profile.org_name ?? 'AgroStake',
        email: profile.email ?? loginEmail.trim().toLowerCase(),
        full_name: profile.full_name ?? 'Usuario AgroStake',
        phone: profile.phone ?? '',
        role: auth.role,
      });
      setLoginPass('');
    } catch (error) {
      setAuthError(error instanceof Error ? error.message : 'No se pudo iniciar sesiÃ³n.');
    }
  };

  const handleRegisterSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setAuthError('');
    if (regFirstName.trim().length < 2 || regLastName.trim().length < 2) {
      setAuthError('Ingresa tu nombre y apellido completos.');
      return;
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(regEmail.trim())) {
      setAuthError('Ingresa un correo electrÃ³nico vÃ¡lido.');
      return;
    }
    const cleanPhone = regPhone.replace(/\D/g, '');
    if (cleanPhone.length !== 10) {
      setAuthError('El nÃºmero telefÃ³nico debe tener 10 dÃ­gitos.');
      return;
    }
    if (regPassword.length < 6) {
      setAuthError('La contraseÃ±a debe tener mÃ­nimo 6 caracteres.');
      return;
    }
    if (regPassword !== regConfirmPass) {
      setAuthError('Las contraseÃ±as no coinciden.');
      return;
    }

    setAuthError(
      'El registro desde esta pantalla todavÃ­a no estÃ¡ conectado al endpoint de registro. Solicita que el administrador cree tu cuenta y despuÃ©s inicia sesiÃ³n.'
    );
  };

  // --- EvaluaciÃ³n de Cultivos con Regla 4/4 del SQL v3.3 ---
  const evaluatedCrops = useMemo(() => {
    return DB_CROPS.map((crop) => {
      const moistRange = computeFao56MoistureRange(crop.depletion_fraction_p, soilTexture);

      const checkVar = (
        variable: VariableCode,
        val: number,
        min: number,
        max: number
      ): { status: CheckStatus; advice: string | null } => {
        if (val >= min && val <= max) return { status: 'in_range', advice: null };
        if (val < min) return { status: 'below', advice: formatAdviceRule(variable, 'below', val, min) };
        return { status: 'above', advice: formatAdviceRule(variable, 'above', val, max) };
      };

      const tempCheck = checkVar('soil_temperature', latest.soil_temperature_c, crop.temp_min, crop.temp_max);
      const moistCheck = checkVar('soil_moisture', latest.soil_moisture_pct, moistRange.minPct, moistRange.maxPct);
      const phCheck = checkVar('soil_ph', latest.soil_ph, crop.ph_min, crop.ph_max);
      const rainCheck = checkVar('rainfall', latest.precip_total_mm, crop.rain_min, crop.rain_max);

      const checks = [
        { variable: 'soil_temperature' as VariableCode, label: 'Temperatura suelo', val: `${latest.soil_temperature_c.toFixed(1)} Â°C`, range: `${crop.temp_min}â€“${crop.temp_max} Â°C`, origin: 'estaca', ...tempCheck },
        { variable: 'soil_moisture' as VariableCode, label: 'Humedad (FAO-56)', val: `${latest.soil_moisture_pct.toFixed(1)} %`, range: `${moistRange.minPct}â€“${moistRange.maxPct} %`, origin: 'estaca', ...moistCheck },
        { variable: 'soil_ph' as VariableCode, label: 'pH Simulado', val: `${latest.soil_ph.toFixed(2)} pH`, range: `${crop.ph_min}â€“${crop.ph_max} pH`, origin: 'simulado', ...phCheck },
        { variable: 'rainfall' as VariableCode, label: 'PrecipitaciÃ³n (30d)', val: `${latest.precip_total_mm.toFixed(1)} mm`, range: `${crop.rain_min}â€“${crop.rain_max} mm`, origin: 'nasa_power', ...rainCheck },
      ];

      const variables_ok = checks.filter((c) => c.status === 'in_range').length;
      const classification: ViabilityClass =
        variables_ok === 4 ? 'recomendado' : variables_ok === 3 ? 'condicionado' : 'no_recomendado';

      const sTemp = calcSoftVariableScore(latest.soil_temperature_c, crop.temp_min, crop.temp_max, 8);
      const sMoist = calcSoftVariableScore(latest.soil_moisture_pct, moistRange.minPct, moistRange.maxPct, 12);
      const sPh = calcSoftVariableScore(latest.soil_ph, crop.ph_min, crop.ph_max, 1.2);
      const sRain = calcSoftVariableScore(latest.precip_total_mm, crop.rain_min, crop.rain_max, 50);
      const ml_suitability_score = Math.round((sTemp + sMoist + sPh + sRain) / 4);

      return {
        crop,
        moistRange,
        checks,
        variables_ok,
        classification,
        ml_suitability_score,
      };
    }).sort((a, b) => b.ml_suitability_score - a.ml_suitability_score);
  }, [latest, soilTexture]);

  const filteredCrops = useMemo(() => {
    return evaluatedCrops.filter((item) => {
      const backendCrop = recommendationRun?.results?.find(
        (result) =>
          result.scientific_name.trim().toLowerCase() ===
          item.crop.scientific_name.trim().toLowerCase()
      );

      const hasCompleteEvaluation = isVerifiedEvaluation(backendCrop);

      const matchesClass =
        cropFilterClass === 'all' ||
        (hasCompleteEvaluation &&
          backendCrop?.classification === cropFilterClass);

      const q = cropSearch.trim().toLowerCase();
      const matchesQuery =
        !q ||
        item.crop.common_name_es.toLowerCase().includes(q) ||
        item.crop.scientific_name.toLowerCase().includes(q) ||
        item.crop.category.toLowerCase().includes(q) ||
        (item.crop.dataset_label &&
          item.crop.dataset_label.toLowerCase().includes(q));

      return matchesClass && matchesQuery;
    });
  }, [evaluatedCrops, recommendationRun, cropFilterClass, cropSearch]);

  // ============================================================================
  // PANTALLA DE LOGIN Y REGISTRO COMPLETA
  // ============================================================================
  if (!user) {
    return (
      <div className="min-h-screen bg-[#EEEEEE] text-[#202020] flex items-center justify-center p-4 font-sans">
        <div className="w-full max-w-md bg-white border border-[#D5D5D5] rounded-2xl shadow-sm p-8">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-10 h-10 rounded-xl bg-[#1E1E1E] text-white flex items-center justify-center">
              <Sprout className="w-5 h-5 text-[#F39200]" />
            </div>
            <div>
              <h1 className="text-lg font-bold tracking-tight text-[#202020]">AgroStake</h1>
              <p className="text-xs text-[#777777]">Monitoreo Inteligente de Suelo Â· v3.3</p>
            </div>
          </div>

          <h2 className="text-xl font-bold text-[#202020] mb-1">
            {authMode === 'login' ? 'Iniciar sesiÃ³n' : 'Crear cuenta de productor'}
          </h2>
          <p className="text-xs text-[#777777] mb-6">
            {authMode === 'login'
              ? 'Ingresa tus credenciales para consultar tu parcela.'
              : 'Completa tus datos para registrar tu organizaciÃ³n en el sistema.'}
          </p>

          {authError && (
            <div className="mb-4 p-3 rounded-xl bg-[#E34545]/10 border border-[#E34545]/30 text-xs font-medium text-[#E34545]">
              {authError}
            </div>
          )}

          {authMode === 'login' ? (
            <form onSubmit={handleLoginSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-[#202020] mb-1.5">Correo electrÃ³nico</label>
                <input
                  type="email"
                  value={loginEmail}
                  onChange={(e) => setLoginEmail(e.target.value)}
                  className="w-full bg-[#F8F8F8] border border-[#D5D5D5] rounded-xl px-3.5 py-2.5 text-sm focus:outline-none focus:border-[#1E1E1E]"
                  required
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-[#202020] mb-1.5">ContraseÃ±a</label>
                <input
                  type="password"
                  value={loginPass}
                  onChange={(e) => setLoginPass(e.target.value)}
                  className="w-full bg-[#F8F8F8] border border-[#D5D5D5] rounded-xl px-3.5 py-2.5 text-sm focus:outline-none focus:border-[#1E1E1E]"
                  required
                />
              </div>
              <button
                type="submit"
                className="w-full py-3 rounded-xl bg-[#F39200] hover:bg-[#e08600] text-[#1E1E1E] font-bold text-sm transition-colors cursor-pointer"
              >
                Entrar al panel
              </button>
              <div className="pt-3 border-t border-[#EEEEEE] text-center">
                <button
                  type="button"
                  onClick={() => {
                    setAuthError('');
                    setAuthMode('register');
                  }}
                  className="text-xs font-semibold text-[#202020] hover:text-[#F39200] transition-colors cursor-pointer"
                >
                  Â¿No tienes cuenta? <span className="underline">Registrarte aquÃ­</span>
                </button>
              </div>
            </form>
          ) : (
            <form onSubmit={handleRegisterSubmit} className="space-y-3.5">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-[#202020] mb-1">Nombre</label>
                  <input
                    type="text"
                    value={regFirstName}
                    onChange={(e) => setRegFirstName(e.target.value)}
                    className="w-full bg-[#F8F8F8] border border-[#D5D5D5] rounded-xl px-3 py-2 text-sm focus:outline-none focus:border-[#1E1E1E]"
                    required
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-[#202020] mb-1">Apellido</label>
                  <input
                    type="text"
                    value={regLastName}
                    onChange={(e) => setRegLastName(e.target.value)}
                    className="w-full bg-[#F8F8F8] border border-[#D5D5D5] rounded-xl px-3 py-2 text-sm focus:outline-none focus:border-[#1E1E1E]"
                    required
                  />
                </div>
              </div>
              <div>
                <label className="block text-xs font-semibold text-[#202020] mb-1">Correo electrÃ³nico</label>
                <input
                  type="email"
                  value={regEmail}
                  onChange={(e) => setRegEmail(e.target.value)}
                  className="w-full bg-[#F8F8F8] border border-[#D5D5D5] rounded-xl px-3 py-2 text-sm focus:outline-none focus:border-[#1E1E1E]"
                  required
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-[#202020] mb-1">TelÃ©fono (10 dÃ­gitos)</label>
                <input
                  type="tel"
                  value={regPhone}
                  onChange={(e) => setRegPhone(e.target.value)}
                  className="w-full bg-[#F8F8F8] border border-[#D5D5D5] rounded-xl px-3 py-2 text-sm focus:outline-none focus:border-[#1E1E1E]"
                  required
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-[#202020] mb-1">ContraseÃ±a</label>
                  <input
                    type="password"
                    value={regPassword}
                    onChange={(e) => setRegPassword(e.target.value)}
                    className="w-full bg-[#F8F8F8] border border-[#D5D5D5] rounded-xl px-3 py-2 text-sm focus:outline-none focus:border-[#1E1E1E]"
                    required
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-[#202020] mb-1">Confirmar</label>
                  <input
                    type="password"
                    value={regConfirmPass}
                    onChange={(e) => setRegConfirmPass(e.target.value)}
                    className="w-full bg-[#F8F8F8] border border-[#D5D5D5] rounded-xl px-3 py-2 text-sm focus:outline-none focus:border-[#1E1E1E]"
                    required
                  />
                </div>
              </div>
              <button
                type="submit"
                className="w-full py-3 rounded-xl bg-[#F39200] hover:bg-[#e08600] text-[#1E1E1E] font-bold text-sm transition-colors cursor-pointer"
              >
                Registrarme y entrar
              </button>
              <div className="pt-2 border-t border-[#EEEEEE] text-center">
                <button
                  type="button"
                  onClick={() => {
                    setAuthError('');
                    setAuthMode('login');
                  }}
                  className="text-xs font-semibold text-[#202020] hover:text-[#F39200] transition-colors cursor-pointer"
                >
                  Â¿Ya tienes cuenta? <span className="underline">Iniciar sesiÃ³n</span>
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    );
  }

  const navItems: { id: typeof activeTab; icon: React.ElementType; label: string }[] = [
    { id: 'home', icon: Home, label: 'Inicio' },
    { id: 'telemetry', icon: Activity, label: 'Valores en vivo' },
    { id: 'crops', icon: Sprout, label: 'Cultivos aptos' },
    { id: 'sensors', icon: Cpu, label: 'Estado de los sensores' },
    { id: 'advice', icon: ClipboardCheck, label: 'Recomendaciones' },
  ];

  return (
    <div className="min-h-screen bg-[#EEEEEE] text-[#202020] flex flex-col font-sans">
      {/* BARRA SUPERIOR: CONEXIÃ“N WIFI / BLUETOOTH ESP32 + ESTADO + BATERÃA */}
      <header className="h-16 bg-white border-b border-[#D5D5D5] px-4 md:px-6 flex items-center justify-between sticky top-0 z-30">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-[#1E1E1E] text-white flex items-center justify-center">
            <Sprout className="w-5 h-5 text-[#F39200]" />
          </div>
          <div>
            <span className="font-bold text-base tracking-tight text-[#202020] block leading-none">AgroStake</span>
            <span className="text-[10px] font-medium text-[#777777]">{deviceUid}</span>
          </div>
        </div>

        <div className="flex items-center gap-2 md:gap-3">
          {/* Selector Wi-Fi / Bluetooth para el ESP32 */}
          <div className="flex items-center bg-[#F4F4F4] border border-[#D5D5D5] rounded-xl p-1 gap-1">
            <button
              type="button"
              onClick={() => {
                setEspTransport('wifi_mqtt');
                setConnectionWarning('');
              }}
              className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
                espTransport === 'wifi_mqtt' && espConnected
                  ? 'bg-[#1E1E1E] text-white shadow-xs'
                  : 'text-[#555555] hover:text-[#202020]'
              }`}
              title="Conectar ESP32 por Wi-Fi (MQTT)"
            >
              <Wifi className="w-3.5 h-3.5 text-[#F39200]" />
              <span className="hidden sm:inline">Wi-Fi</span>
            </button>
            <button
              type="button"
              onClick={() => {
                setEspTransport('ble');
                setConnectionWarning('');
              }}
              className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
                espTransport === 'ble' && espConnected
                  ? 'bg-[#1E1E1E] text-white shadow-xs'
                  : 'text-[#555555] hover:text-[#202020]'
              }`}
              title="Conectar ESP32 por Bluetooth (BLE)"
            >
              <Bluetooth className="w-3.5 h-3.5 text-[#F39200]" />
              <span className="hidden sm:inline">Bluetooth</span>
            </button>
          </div>

          {/* Estado obtenido del backend; no activa datos demo */}
          <span
            className={`px-2.5 py-1.5 rounded-lg text-[11px] font-bold border ${
              espConnected
                ? 'bg-[#159447]/10 text-[#159447] border-[#159447]/30'
                : 'bg-[#E34545]/10 text-[#E34545] border-[#E34545]/30'
            }`}
            title={telemetryError || 'Estado calculado a partir de la Ãºltima lectura real'}
          >
            {espConnected ? 'ESP32 conectado' : 'Esperando ESP32'}
          </span>

          <span
            className="inline-flex items-center rounded-lg border border-[#D5D5D5] bg-[#F8F8F8] px-2.5 py-1.5 text-[11px] font-semibold text-[#777777]"
            title="El firmware actual no envÃ­a voltaje de baterÃ­a."
          >
            BaterÃ­a: N/D
          </span>

          <button
            onClick={() => {
              setUser(null);
              setAccessToken(null);
              setParcels([]);
              setIsAnalysisActive(false);
              setShowDurationModal(false);
            }}
            className="w-9 h-9 rounded-xl bg-[#E2E2E2] hover:bg-[#1E1E1E] text-[#202020] hover:text-white flex items-center justify-center transition-colors cursor-pointer"
            title="Cerrar sesiÃ³n"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </header>

      <div className="flex-1 flex">
        {/* SIDEBAR IZQUIERDO */}
        <aside className="w-20 bg-white border-r border-[#D5D5D5] flex flex-col items-center justify-start pt-5 gap-3 sticky top-16 h-[calc(100vh-4rem)] shrink-0">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isSelected = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setActiveTab(item.id)}
                title={item.label}
                className={`w-12 h-12 rounded-xl flex items-center justify-center transition-all cursor-pointer relative ${
                  isSelected
                    ? 'bg-[#1E1E1E] text-white shadow-sm'
                    : 'bg-[#E2E2E2] text-[#202020] hover:bg-[#1E1E1E] hover:text-white'
                }`}
              >
                <Icon className="w-5 h-5 stroke-[2]" />
                {item.id === 'telemetry' && isAnalysisActive && (
                  <span className="w-2.5 h-2.5 rounded-full bg-[#159447] border-2 border-white absolute top-1.5 right-1.5" />
                )}
              </button>
            );
          })}
        </aside>

        {/* CONTENIDO PRINCIPAL */}
        <main className="flex-1 p-6 md:p-8 max-w-5xl mx-auto w-full">
          {/* ==================================================================
              VISTA 1: INICIO (LOS 3 PASOS + BOTÃ“N DE ANÃLISIS CON DURACIÃ“N Y VALIDACIÃ“N)
             ================================================================== */}
          {activeTab === 'home' && (
            <React.Fragment>
              {nasaClimatePanel}
              {backendRecommendationsPanel}
            <section className="space-y-4">
              <div className="bg-white border border-[#D5D5D5] rounded-2xl p-5 shadow-sm">
                <div className="flex flex-wrap items-start justify-between gap-3 mb-4">
                  <div>
                    <p className="text-[11px] uppercase tracking-wider font-bold text-[#F39200]">Cuenta conectada</p>
                    <h2 className="text-lg font-bold text-[#202020]">{user.org_name}</h2>
                    <p className="text-xs text-[#777777]">{user.full_name} Â· {user.email} Â· Rol: {user.role}</p>
                  </div>
                  <span className="inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[11px] font-bold bg-[#159447]/10 text-[#159447]">
                    <CheckCircle2 className="w-3.5 h-3.5" /> SesiÃ³n autenticada
                  </span>
                </div>

                <div className="flex items-center justify-between gap-3 mb-3">
                  <div>
                    <h3 className="text-sm font-bold text-[#202020]">Mis parcelas</h3>
                    <p className="text-xs text-[#777777]">InformaciÃ³n consultada desde el backend de negocio.</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      if (accessToken) {
                        setParcelError('');
                        setIsLoadingParcels(true);
                        getParcels(accessToken)
                          .then(setParcels)
                          .catch((error) => setParcelError(error instanceof Error ? error.message : 'Error al actualizar parcelas.'))
                          .finally(() => setIsLoadingParcels(false));
                      }
                    }}
                    disabled={isLoadingParcels || !accessToken}
                    className="text-xs font-semibold px-3 py-2 rounded-lg border border-[#D5D5D5] hover:bg-[#F4F4F4] disabled:opacity-50"
                  >
                    {isLoadingParcels ? 'Actualizandoâ€¦' : 'Actualizar'}
                  </button>
                </div>

                {isLoadingParcels && (
                  <div className="flex items-center gap-2 text-xs text-[#777777] py-4">
                    <Loader2 className="w-4 h-4 animate-spin text-[#F39200]" /> Consultando parcelasâ€¦
                  </div>
                )}
                {!isLoadingParcels && parcelError && (
                  <div className="p-3 rounded-xl bg-[#E34545]/10 border border-[#E34545]/30 text-xs text-[#B42318]">
                    <strong>No se pudieron cargar las parcelas.</strong> {parcelError}
                    <p className="mt-1 text-[#777777]">Verifica que el backend de negocio estÃ© activo en el puerto 8002 y que permita el origen del frontend.</p>
                  </div>
                )}
                {!isLoadingParcels && !parcelError && parcels.length === 0 && (
                  <div className="p-4 rounded-xl bg-[#F8F8F8] border border-dashed border-[#D5D5D5] text-xs text-[#777777]">
                    Esta organizaciÃ³n todavÃ­a no tiene parcelas registradas.
                  </div>
                )}
                {!isLoadingParcels && parcels.length > 0 && (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {parcels.map((parcel) => (
                      <article key={parcel.id} className="rounded-xl border border-[#E5E5E5] bg-[#F8F8F8] p-4">
                        <div className="flex items-start justify-between gap-2">
                          <div>
                            <h4 className="text-sm font-bold text-[#202020]">{parcel.name}</h4>
                            <p className="text-[10px] text-[#777777] mt-0.5">ID: {parcel.id}</p>
                          </div>
                          <Sprout className="w-5 h-5 text-[#F39200]" />
                        </div>
                        <div className="grid grid-cols-2 gap-3 mt-4">
                          <div>
                            <p className="text-[10px] text-[#777777]">Superficie</p>
                            <p className="text-sm font-bold text-[#202020]">{parcel.area_ha} ha</p>
                          </div>
                          <div>
                            <p className="text-[10px] text-[#777777]">Estacas activas</p>
                            <p className="text-sm font-bold text-[#202020]">{parcel.active_stakes}</p>
                          </div>
                          <div>
                            <p className="text-[10px] text-[#777777]">Alertas abiertas</p>
                            <p className="text-sm font-bold text-[#202020]">{parcel.open_alerts}</p>
                          </div>
                          <div>
                            <p className="text-[10px] text-[#777777]">Textura</p>
                            <p className="text-sm font-bold text-[#202020]">{parcel.soil_texture_name || parcel.soil_texture || 'Sin definir'}</p>
                          </div>
                        </div>
                        <p className="text-[10px] text-[#777777] mt-3">
                          Coordenadas: {Number(parcel.latitude).toFixed(4)}, {Number(parcel.longitude).toFixed(4)}
                        </p>
                      </article>
                    ))}
                  </div>
                )}
              </div>

              <div className="bg-white border border-[#D5D5D5] rounded-2xl p-6 md:p-8 shadow-sm">
              <div className="max-w-2xl mx-auto text-center mb-6">
                <span className="inline-block text-[11px] font-bold uppercase tracking-wider text-[#F39200] bg-[#F39200]/10 px-3 py-1 rounded-full mb-2">
                  GuÃ­a de uso rÃ¡pido
                </span>
                <h1 className="text-2xl md:text-3xl font-bold text-[#202020] tracking-tight">
                  Conoce el estado de tu tierra antes de sembrar
                </h1>
                <p className="text-sm text-[#777777] mt-2 leading-relaxed">
                  La estaca revisa la humedad y la temperatura directamente en la zona donde crecen las raÃ­ces, ayudÃ¡ndote a elegir el mejor cultivo y saber cuÃ¡ndo regar.
                </p>
              </div>

              <div className="max-w-lg mx-auto mb-8">
                <StakePhotoDisplay />
              </div>

              <div className="mb-5 rounded-xl border border-[#E9A11B]/30 bg-[#E9A11B]/10 px-4 py-3 text-xs text-[#7A5200]">
                Las parcelas y la telemetrÃ­a fÃ­sica del ESP32 se consultan desde el backend. El pH continÃºa identificado como simulado y la precipitaciÃ³n procede de NASA POWER.
              </div>

              {/* Los 3 pasos originales */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
                <div className="bg-[#F8F8F8] border border-[#E5E5E5] rounded-xl p-4">
                  <div className="w-7 h-7 rounded-lg bg-[#1E1E1E] text-white text-xs font-bold flex items-center justify-center mb-2.5">
                    1
                  </div>
                  <h3 className="text-sm font-bold text-[#202020] mb-1">Coloca la estaca en el terreno</h3>
                  <p className="text-xs text-[#777777] leading-relaxed">
                    EntiÃ©rrala de forma vertical en el lugar donde planeas sembrar, procurando que las puntas metÃ¡licas entren completas en la tierra hÃºmeda.
                  </p>
                </div>

                <div className="bg-[#F8F8F8] border border-[#E5E5E5] rounded-xl p-4">
                  <div className="w-7 h-7 rounded-lg bg-[#1E1E1E] text-white text-xs font-bold flex items-center justify-center mb-2.5">
                    2
                  </div>
                  <h3 className="text-sm font-bold text-[#202020] mb-1">Enciende e inicia la lectura</h3>
                  <p className="text-xs text-[#777777] leading-relaxed">
                    Verifica arriba que tu estaca estÃ© conectada por Wi-Fi o Bluetooth y presiona el botÃ³n naranja para elegir la duraciÃ³n del anÃ¡lisis.
                  </p>
                </div>

                <div className="bg-[#F8F8F8] border border-[#E5E5E5] rounded-xl p-4">
                  <div className="w-7 h-7 rounded-lg bg-[#1E1E1E] text-white text-xs font-bold flex items-center justify-center mb-2.5">
                    3
                  </div>
                  <h3 className="text-sm font-bold text-[#202020] mb-1">Revisa quÃ© sembrar y cÃ³mo cuidar</h3>
                  <p className="text-xs text-[#777777] leading-relaxed">
                    Consulta en los iconos de la izquierda quÃ© semillas se adaptan mejor a tu tierra hoy y quÃ© ajustes sencillos puedes aplicar.
                  </p>
                </div>
              </div>

              {/* Alerta si intenta iniciar anÃ¡lisis con el ESP32 desconectado */}
              {connectionWarning && (
                <div className="max-w-lg mx-auto mb-4 p-3.5 rounded-xl bg-[#E34545]/10 border border-[#E34545]/30 flex items-center gap-2.5 text-xs font-semibold text-[#E34545]">
                  <AlertTriangle className="w-4 h-4 shrink-0" />
                  <span>{connectionWarning}</span>
                </div>
              )}

              {/* Ãrea del botÃ³n Ãºnico de AnÃ¡lisis */}
              <div className="flex flex-col items-center">
                {!isAnalysisActive ? (
                  !showDurationModal && !isBootingAnalysis ? (
                    <button
                      type="button"
                      onClick={handleClickInitAnalysisButton}
                      className="inline-flex items-center gap-3 px-8 py-4 rounded-xl bg-[#F39200] hover:bg-[#e08600] text-[#1E1E1E] font-bold text-sm shadow-sm transition-all cursor-pointer"
                    >
                      <Play className="w-5 h-5 fill-current" />
                      <span>Iniciar anÃ¡lisis</span>
                    </button>
                  ) : isBootingAnalysis ? (
                    <div className="w-full max-w-md bg-[#F8F8F8] border border-[#DEDEDE] rounded-xl p-4 text-center">
                      <div className="flex items-center justify-center gap-2 text-xs font-bold text-[#202020]">
                        <Loader2 className="w-4 h-4 animate-spin text-[#F39200]" />
                        <span>{analysisStepText}</span>
                      </div>
                      <div className="w-full h-1.5 bg-[#DEDEDE] rounded-full overflow-hidden mt-2.5">
                        <div className="h-full bg-[#F39200] animate-pulse w-4/5 rounded-full" />
                      </div>
                    </div>
                  ) : (
                    /* Selector emergente de duraciÃ³n al hacer clic en Iniciar anÃ¡lisis */
                    <div className="w-full max-w-md bg-[#F8F8F8] border border-[#D5D5D5] rounded-2xl p-5 text-center space-y-3">
                      <div className="flex items-center justify-center gap-1.5 text-xs font-bold text-[#202020]">
                        <Clock className="w-4 h-4 text-[#F39200]" />
                        <span>Selecciona la duraciÃ³n del anÃ¡lisis</span>
                      </div>
                      <p className="text-[11px] text-[#777777]">
                        El anÃ¡lisis se detendrÃ¡ automÃ¡ticamente al terminar el tiempo o cuando lo pauses manualmente.
                      </p>
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1">
                        {[
                          { label: '1 min', sec: 60 },
                          { label: '5 min', sec: 300 },
                          { label: '15 min', sec: 900 },
                          { label: 'Continuo', sec: 0 },
                        ].map((opt) => (
                          <button
                            key={opt.sec}
                            type="button"
                            onClick={() => handleConfirmDurationAndStart(opt.sec)}
                            className="py-2.5 px-3 rounded-xl bg-white hover:bg-[#1E1E1E] text-[#202020] hover:text-white border border-[#D5D5D5] text-xs font-bold transition-colors cursor-pointer"
                          >
                            {opt.label}
                          </button>
                        ))}
                      </div>
                      <button
                        type="button"
                        onClick={() => setShowDurationModal(false)}
                        className="text-xs font-semibold text-[#777777] hover:text-[#202020] underline cursor-pointer pt-1"
                      >
                        Cancelar
                      </button>
                    </div>
                  )
                ) : (
                  /* Si el usuario regresa al Home mientras el anÃ¡lisis corre, puede detenerlo aquÃ­ mismo */
                  <div className="flex flex-col items-center gap-2">
                    <button
                      type="button"
                      onClick={handleStopAnalysis}
                      className="inline-flex items-center gap-3 px-8 py-4 rounded-xl bg-[#E34545] hover:bg-[#c93737] text-white font-bold text-sm shadow-sm transition-all cursor-pointer"
                    >
                      <Square className="w-4 h-4 fill-current" />
                      <span>
                        Detener anÃ¡lisis (
                        {remainingSec !== null
                          ? `Restan ${formatSeconds(remainingSec)}`
                          : `Continuo Â· ${formatSeconds(elapsedSec)}`}
                        )
                      </span>
                    </button>
                    <span className="text-xs text-[#777777]">
                      ConexiÃ³n real por {espTransport === 'wifi_mqtt' ? 'Wi-Fi' : 'Bluetooth (BLE)'}
                    </span>
                  </div>
                )}
              </div>
              </div>
            </section>
            </React.Fragment>
          )}

          {/* ==================================================================
              VISTA 2: VALORES EN VIVO (4 TARJETAS + 1 SOLA GRÃFICA CON NÃšMEROS + HISTORIAL DESPLEGABLE)
             ================================================================== */}
          {activeTab === 'telemetry' && (
            <section className="space-y-6">
              {/* Encabezado y controles */}
              <div className="bg-white border border-[#D5D5D5] rounded-2xl p-5 flex flex-wrap items-center justify-between gap-4">
                <div>
                  <div className="flex items-center gap-2">
                    <h2 className="text-xl font-bold text-[#202020]">Monitoreo del suelo</h2>
                    <span
                      className={`text-[11px] font-bold px-2.5 py-0.5 rounded-full ${
                        isAnalysisActive && espConnected
                          ? 'bg-[#159447]/15 text-[#159447]'
                          : 'bg-[#E9A11B]/15 text-[#E9A11B]'
                      }`}
                    >
                      {isAnalysisActive && espConnected
                        ? remainingSec !== null
                          ? `Analizando Â· ${formatSeconds(remainingSec)}`
                          : `En ejecuciÃ³n Â· ${formatSeconds(elapsedSec)}`
                        : 'En espera'}
                    </span>
                  </div>
                  <p className="text-xs text-[#777777] mt-0.5">
                    Datos reales Â· Transporte: <strong>{espTransport === 'wifi_mqtt' ? 'Wi-Fi (MQTT)' : 'Bluetooth (BLE)'}</strong> Â·
                    Frecuencia de actualizaciÃ³n: {sampleIntervalSec}s
                  </p>
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  <select
                    value={soilTexture}
                    onChange={(e) => setSoilTexture(e.target.value as SoilTextureCode)}
                    className="bg-[#F8F8F8] border border-[#D5D5D5] rounded-xl px-3 py-2 text-xs font-semibold text-[#202020] focus:outline-none cursor-pointer"
                  >
                    {Object.values(SOIL_TEXTURES).map((t) => (
                      <option key={t.texture_code} value={t.texture_code}>
                        Tierra: {t.name_es}
                      </option>
                    ))}
                  </select>

                  {!isConfiguringTime ? (
                    <button
                      onClick={() => setIsConfiguringTime(true)}
                      className="inline-flex items-center gap-2 px-3.5 py-2 rounded-xl bg-[#1E1E1E] text-white text-xs font-semibold hover:bg-black transition-colors cursor-pointer"
                    >
                      <Settings className="w-3.5 h-3.5 text-[#F39200]" />
                      <span>Tiempo: {sampleIntervalSec}s</span>
                    </button>
                  ) : (
                    <div className="flex items-center gap-1.5 bg-[#F8F8F8] border border-[#F39200] rounded-xl p-1">
                      <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-[#E9A11B] px-2">
                        <Pause className="w-3 h-3" /> Pausa:
                      </span>
                      {[2, 5, 10].map((sec) => (
                        <button
                          key={sec}
                          onClick={() => {
                            setSampleIntervalSec(sec);
                            setIsConfiguringTime(false);
                          }}
                          className={`px-2.5 py-1 rounded-lg text-xs font-bold transition-colors cursor-pointer ${
                            sampleIntervalSec === sec
                              ? 'bg-[#F39200] text-[#1E1E1E]'
                              : 'bg-white text-[#202020] hover:bg-[#E2E2E2]'
                          }`}
                        >
                          {sec}s
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              {/* Las 4 Tarjetas de Lectura */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                <div className="bg-white border border-[#D5D5D5] rounded-2xl p-5">
                  <div className="flex items-center justify-between text-xs font-semibold text-[#777777] mb-2">
                    <span>Temperatura Suelo</span>
                    <Thermometer className="w-4 h-4 text-[#F39200]" />
                  </div>
                  <div className="flex items-baseline gap-1">
                    <span className="text-3xl font-bold text-[#202020] tabular-nums">
                      {espConnected ? latest.soil_temperature_c.toFixed(1) : 'N/D'}
                    </span>
                    <span className="text-sm font-semibold text-[#777777]">Â°C</span>
                  </div>
                  <span className="inline-block mt-3 text-[11px] font-semibold text-[#159447]">
                    Lectura fÃ­sica Â· DS18B20
                  </span>
                </div>

                <div className="bg-white border border-[#D5D5D5] rounded-2xl p-5">
                  <div className="flex items-center justify-between text-xs font-semibold text-[#777777] mb-2">
                    <span>Humedad Suelo</span>
                    <Droplets className="w-4 h-4 text-[#202020]" />
                  </div>
                  <div className="flex items-baseline gap-1">
                    <span className="text-3xl font-bold text-[#202020] tabular-nums">
                      {espConnected ? latest.soil_moisture_pct.toFixed(1) : 'N/D'}
                    </span>
                    <span className="text-sm font-semibold text-[#777777]">% vol</span>
                  </div>
                  <span className="inline-block mt-3 text-[11px] font-semibold text-[#777777]">
                    Lectura fÃ­sica Â· ADC del sensor resistivo
                  </span>
                </div>

                <div className="bg-white border border-[#D5D5D5] rounded-2xl p-5">
                  <div className="flex items-center justify-between text-xs font-semibold text-[#777777] mb-2">
                    <span>Nivel de pH (Simulado)</span>
                    <FlaskConical className="w-4 h-4 text-[#F39200]" />
                  </div>
                  <div className="flex items-baseline gap-1">
                    <span className="text-3xl font-bold text-[#202020] tabular-nums">
                      {espConnected ? latest.soil_ph.toFixed(2) : 'N/D'}
                    </span>
                    <span className="text-sm font-semibold text-[#777777]">pH</span>
                  </div>
                  <span className="inline-block mt-3 text-[11px] font-semibold text-[#E9A11B]">
                    MÃ©todo: simulado (v3.3)
                  </span>
                </div>

                <div className="bg-white border border-[#D5D5D5] rounded-2xl p-5">
                  <div className="flex items-center justify-between text-xs font-semibold text-[#777777] mb-2">
                    <span>PrecipitaciÃ³n (30d)</span>
                    <CloudRain className="w-4 h-4 text-[#159447]" />
                  </div>
                  <div className="flex items-baseline gap-1">
                    <span className="text-3xl font-bold text-[#202020] tabular-nums">
                      {climateSummary?.rainfall_30d?.precip_total_mm != null ? climateSummary.rainfall_30d.precip_total_mm.toFixed(2) : 'N/D'}
                    </span>
                    <span className="text-sm font-semibold text-[#777777]">mm</span>
                  </div>
                  <span className="inline-block mt-3 text-[11px] font-semibold text-[#159447]">
                    NASA POWER (MERRA-2)
                    {climateSummary?.rainfall_30d?.last_valid_date && (
                      <span className="block mt-1 text-[#777777] font-normal">
                        Ãšltima observaciÃ³n: {climateSummary.rainfall_30d.last_valid_date}
                      </span>
                    )}
                  </span>
                </div>
              </div>

              {/* Historial real de precipitaciÃ³n NASA POWER */}
              <section className="bg-white border border-[#D5D5D5] rounded-2xl p-6">
                <h3 className="text-sm font-bold text-[#202020] mb-1">
                  Historial de precipitaciÃ³n - NASA POWER
                </h3>
                <p className="text-xs text-[#777777] mb-4">
                  PrecipitaciÃ³n diaria en mm. Los dÃ­as sin datos se muestran como N/D.
                </p>

                {climateHistory.length === 0 ? (
                  <p className="text-sm text-[#777777]">
                    No hay historial climÃ¡tico disponible.
                  </p>
                ) : (
                  <div className="w-full overflow-x-auto">
                    <div className="flex items-end gap-1 h-44 min-w-[600px] border-b border-[#D5D5D5] pb-2">
                      {climateHistory.map((day) => {
                        const maxRain = Math.max(
                          1,
                          ...climateHistory
                            .map((item) => item.precip_mm)
                            .filter((value): value is number => value != null)
                        );

                        return (
                          <div
                            key={day.obs_date}
                            className="flex-1 flex flex-col justify-end items-center h-full min-w-[12px]"
                            title={`${day.obs_date}: ${day.precip_mm == null ? 'Sin datos' : `${day.precip_mm.toFixed(2)} mm`}`}
                          >
                            {day.precip_mm == null ? (
                              <div className="w-full text-center text-[9px] text-[#999999]">
                                N/D
                              </div>
                            ) : (
                              <div
                                className="w-full bg-[#159447] rounded-t-sm"
                                style={{
                                  height: `${Math.max(2, (day.precip_mm / maxRain) * 135)}px`,
                                }}
                              />
                            )}
                          </div>
                        );
                      })}
                    </div>
                    <div className="flex justify-between mt-2 text-[10px] text-[#777777]">
                      <span>{climateHistory[0]?.obs_date}</span>
                      <span>{climateHistory[climateHistory.length - 1]?.obs_date}</span>
                    </div>
                  </div>
                )}
                <p className="text-xs text-[#159447] font-semibold mt-3">
                  Fuente: NASA POWER Â· PrecipitaciÃ³n diaria, no acumulada
                </p>
              </section>
              {/* UNA SOLA GRÃFICA UNIFICADA CON LAS 4 MÃ‰TRICAS Y NÃšMEROS VISIBLES */}
              {espConnected ? (
<div className="bg-white border border-[#D5D5D5] rounded-2xl p-6">
                <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
                  <div>
                    <h3 className="text-sm font-bold text-[#202020]">
                      TelemetrÃ­a ESP32 (temperatura y humedad reales)
                    </h3>
                    <p className="text-xs text-[#777777]">
                      Temperatura y humedad recibidas del ESP32. pH y lluvia se muestran como fuentes independientes.
                    </p>
                  </div>

                  {/* Leyenda con los nÃºmeros actuales en vivo */}
                  <div className="flex flex-wrap items-center gap-3 text-xs font-bold bg-[#F8F8F8] border border-[#E5E5E5] px-3 py-2 rounded-xl">
                    <span className="flex items-center gap-1.5 text-[#202020]">
                      <span className="w-3 h-1 bg-[#F39200] rounded-full inline-block" />
                      Temp: {latest.soil_temperature_c.toFixed(1)}Â°C
                    </span>
                    <span className="flex items-center gap-1.5 text-[#202020]">
                      <span className="w-3 h-1 bg-[#1E1E1E] rounded-full inline-block" />
                      Hum: {latest.soil_moisture_pct.toFixed(1)}%
                    </span>
                    <span className="flex items-center gap-1.5 text-[#202020]">
                      <span className="w-3 h-1 bg-[#2563EB] rounded-full inline-block" />
                      pH Sim (x10): {latest.soil_ph.toFixed(2)}
                    </span>
                    <span className="flex items-center gap-1.5 text-[#202020]">
                      <span className="w-3 h-1 bg-[#159447] rounded-full inline-block" />
                      Lluvia simulada: {latest.precip_total_mm.toFixed(1)}mm
                    </span>
                  </div>
                </div>

                <div className="w-full bg-[#F8F8F8] border border-[#E5E5E5] rounded-xl p-4">
                  <svg viewBox="0 0 660 230" className="w-full h-64 overflow-visible">
                    {/* Eje Y con nÃºmeros claros (0, 25, 50, 75, 100) */}
                    {[
                      { val: 100, y: 15 },
                      { val: 75, y: 60 },
                      { val: 50, y: 105 },
                      { val: 25, y: 150 },
                      { val: 0, y: 195 },
                    ].map((tick) => (
                      <g key={tick.val}>
                        <text
                          x="28"
                          y={tick.y + 4}
                          textAnchor="end"
                          className="text-[11px] fill-[#555555] font-bold"
                        >
                          {tick.val}
                        </text>
                        <line
                          x1="36"
                          y1={tick.y}
                          x2="610"
                          y2={tick.y}
                          stroke="#DEDEDE"
                          strokeDasharray="3 3"
                        />
                      </g>
                    ))}

                    {/* Etiquetas numÃ©ricas de tiempo en el Eje X */}
                    {history.map((pt, i) => {
                      if (i % 3 !== 0 && i !== history.length - 1) return null;
                      const x = 36 + (i / Math.max(1, history.length - 1)) * 574;
                      return (
                        <text
                          key={i}
                          x={x}
                          y="218"
                          textAnchor="middle"
                          className="text-[10px] fill-[#777777] font-semibold"
                        >
                          {pt.timeLabel}
                        </text>
                      );
                    })}

                    {/* Curva 1: PrecipitaciÃ³n NASA POWER */}
                    <polyline
                      fill="none"
                      stroke="#159447"
                      strokeWidth="2.4"
                      points={history
                        .map((pt, i) => {
                          const x = 36 + (i / Math.max(1, history.length - 1)) * 574;
                          const y = 195 - (Math.min(100, Math.max(0, pt.precip_total_mm)) / 100) * 180;
                          return `${x},${y}`;
                        })
                        .join(' ')}
                    />
                    {/* Curva 2: pH Simulado (multiplicado x10 para verse claro en la escala 0-100) */}
                    <polyline
                      fill="none"
                      stroke="#2563EB"
                      strokeWidth="2.4"
                      points={history
                        .map((pt, i) => {
                          const x = 36 + (i / Math.max(1, history.length - 1)) * 574;
                          const y = 195 - (Math.min(100, Math.max(0, pt.soil_ph * 10)) / 100) * 180;
                          return `${x},${y}`;
                        })
                        .join(' ')}
                    />

                    {/* Curva 3: Temperatura (Â°C, escala directa 0-100) */}
                    <polyline
                      fill="none"
                      stroke="#F39200"
                      strokeWidth="2.6"
                      points={history
                        .map((pt, i) => {
                          const x = 36 + (i / Math.max(1, history.length - 1)) * 574;
                          const y = 195 - (Math.min(100, Math.max(0, pt.soil_temperature_c)) / 100) * 180;
                          return `${x},${y}`;
                        })
                        .join(' ')}
                    />

                    {/* Curva 4: Humedad (% vol, escala directa 0-100) */}
                    <polyline
                      fill="none"
                      stroke="#1E1E1E"
                      strokeWidth="2.6"
                      points={history
                        .map((pt, i) => {
                          const x = 36 + (i / Math.max(1, history.length - 1)) * 574;
                          const y = 195 - (Math.min(100, Math.max(0, pt.soil_moisture_pct)) / 100) * 180;
                          return `${x},${y}`;
                        })
                        .join(' ')}
                    />

                    {/* Valores numÃ©ricos al final de cada lÃ­nea */}
                    {(() => {
                      const yRain = 195 - (Math.min(100, Math.max(0, latest.precip_total_mm)) / 100) * 180;
                      const yPh = 195 - (Math.min(100, Math.max(0, latest.soil_ph * 10)) / 100) * 180;
                      const yTemp = 195 - (Math.min(100, Math.max(0, latest.soil_temperature_c)) / 100) * 180;
                      const yMoist = 195 - (Math.min(100, Math.max(0, latest.soil_moisture_pct)) / 100) * 180;
                      return (
                        <g className="text-[10px] font-bold">
                          <circle cx="610" cy={yRain} r="3.5" fill="#159447" />
                          <text x="616" y={yRain + 3} fill="#159447">{latest.precip_total_mm.toFixed(0)}mm</text>

                          <circle cx="610" cy={yPh} r="3.5" fill="#2563EB" />
                          <text x="616" y={yPh + 3} fill="#2563EB">pH {latest.soil_ph.toFixed(1)}</text>

                          <circle cx="610" cy={yTemp} r="3.5" fill="#F39200" />
                          <text x="616" y={yTemp + 3} fill="#F39200">{latest.soil_temperature_c.toFixed(1)}Â°C</text>

                          <circle cx="610" cy={yMoist} r="3.5" fill="#1E1E1E" />
                          <text x="616" y={yMoist + 3} fill="#1E1E1E">{latest.soil_moisture_pct.toFixed(1)}%</text>
                        </g>
                      );
                    })()}
                  </svg>
                </div>
              </div>
) : (
  <div className="bg-white border border-[#D5D5D5] rounded-2xl p-6">
    <h3 className="text-sm font-bold text-[#202020]">
      TelemetrÃ­a ESP32
    </h3>
    <p className="text-sm text-[#777777] mt-2">
      Esperando telemetrÃ­a fÃ­sica del ESP32. Comprueba que el dispositivo estÃ© enviando datos al backend.
    </p>
  </div>
)}
{/* HISTORIAL DESPLEGABLE PARA QUE NO ESTORBE */}
              {espConnected ? (
<details className="bg-white border border-[#D5D5D5] rounded-2xl group overflow-hidden">
                <summary className="p-5 font-bold text-sm text-[#202020] cursor-pointer flex items-center justify-between hover:bg-[#F8F8F8] transition-colors list-none">
                  <div className="flex items-center gap-2.5">
                    <List className="w-4 h-4 text-[#F39200]" />
                    <span>Historial de telemetrÃ­a del ESP32 ({history.length} muestras recientes)</span>
                  </div>
                  <ChevronDown className="w-4 h-4 text-[#777777] group-open:rotate-180 transition-transform" />
                </summary>

                <div className="px-5 pb-5 pt-2 border-t border-[#EEEEEE] overflow-x-auto">
                  <table className="w-full text-left border-collapse text-xs">
                    <thead>
                      <tr className="bg-[#F4F4F4] text-[#555555] border-b border-[#E5E5E5]">
                        <th className="py-2.5 px-3 font-bold">Hora</th>
                        <th className="py-2.5 px-3 font-bold">Transporte</th>
                        <th className="py-2.5 px-3 font-bold">Temperatura (Â°C)</th>
                        <th className="py-2.5 px-3 font-bold">Humedad (% vol)</th>
                        <th className="py-2.5 px-3 font-bold">pH (Simulado)</th>
                        <th className="py-2.5 px-3 font-bold">Lluvia simulada (mm)</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[#EEEEEE]">
                      {history
                        .slice()
                        .reverse()
                        .map((row, idx) => (
                          <tr key={idx} className="hover:bg-[#F8F8F8]">
                            <td className="py-2 px-3 font-medium text-[#555555] tabular-nums">{row.timeLabel}</td>
                            <td className="py-2 px-3">
                              <span className="inline-block px-2 py-0.5 rounded bg-[#EEEEEE] text-[#202020] font-semibold text-[11px]">
                                {row.transport === 'wifi_mqtt' ? 'Wi-Fi' : 'BLE'}
                              </span>
                            </td>
                            <td className="py-2 px-3 font-bold text-[#F39200] tabular-nums">
                              {row.soil_temperature_c.toFixed(1)} Â°C
                            </td>
                            <td className="py-2 px-3 font-bold text-[#202020] tabular-nums">
                              {row.soil_moisture_pct.toFixed(1)} %
                            </td>
                            <td className="py-2 px-3 font-bold text-[#2563EB] tabular-nums">
                              {row.soil_ph.toFixed(2)} pH
                            </td>
                            <td className="py-2 px-3 font-bold text-[#159447] tabular-nums">
                              {row.precip_total_mm.toFixed(1)} mm
                            </td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                </div>
              </details>
) : (
  <div className="bg-white border border-[#D5D5D5] rounded-2xl p-5">
    <h3 className="text-sm font-bold text-[#202020]">
      Historial de telemetrÃ­a ESP32
    </h3>
    <p className="text-sm text-[#777777] mt-2">
      No hay lecturas fÃ­sicas recientes del ESP32 para mostrar.
    </p>
  </div>
)}
            </section>
          )}

          {/* ==================================================================
              VISTA 3: CULTIVOS APTOS (SOBRIO, SIN FOTOS, PREPARADO PARA DATASET)
             ================================================================== */}
          {activeTab === 'crops' && (
            <section className="space-y-4">
              <div className="bg-white border border-[#D5D5D5] rounded-2xl p-6 flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                  <h2 className="text-xl font-bold text-[#202020]">Cultivos aptos</h2>
                  <p className="text-xs text-[#777777] mt-1">
                    EvaluaciÃ³n tÃ©cnica sobre las 4 variables (Suelo {SOIL_TEXTURES[soilTexture].name_es}). Listo para cargar Dataset_Crop.csv.
                  </p>
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  <div className="relative">
                    <Search className="w-3.5 h-3.5 text-[#777777] absolute left-3 top-1/2 -translate-y-1/2" />
                    <input
                      type="text"
                      value={cropSearch}
                      onChange={(e) => setCropSearch(e.target.value)}
                      placeholder="Buscar cultivo o etiqueta..."
                      className="bg-[#F8F8F8] border border-[#D5D5D5] rounded-xl pl-8 pr-3 py-1.5 text-xs text-[#202020] focus:outline-none focus:border-[#1E1E1E]"
                    />
                  </div>

                  <select
                    value={cropFilterClass}
                    onChange={(e) => setCropFilterClass(e.target.value as 'all' | ViabilityClass)}
                    className="bg-[#F8F8F8] border border-[#D5D5D5] rounded-xl px-3 py-1.5 text-xs font-semibold text-[#202020] focus:outline-none cursor-pointer"
                  >
                    <option value="all">Todos ({evaluatedCrops.length})</option>
                    <option value="recomendado">Recomendados (datos completos)</option>
                    <option value="condicionado">Condicionados (datos completos)</option>
                    <option value="no_recomendado">No recomendados (datos completos)</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {filteredCrops.map(({ crop, checks, classification }) => {
                  const isExpanded = expandedCropId === crop.id;

                  const backendCrop = recommendationRun?.results?.find(
                    (item) =>
                      item.scientific_name.trim().toLowerCase() ===
                      crop.scientific_name.trim().toLowerCase()
                  );

                  const hasIncompleteEvaluation = !isVerifiedEvaluation(backendCrop);


                  const verifiedClassification =
                    !hasIncompleteEvaluation &&
                    ['recomendado', 'condicionado', 'no_recomendado'].includes(backendCrop?.classification ?? '')
                      ? backendCrop!.classification
                      : null;

                  const verifiedScore =
                    verifiedClassification !== null &&
                    typeof backendCrop?.ml_suitability_score === 'number' &&
                    Number.isFinite(backendCrop.ml_suitability_score) &&
                    backendCrop.ml_suitability_score >= 0 &&
                    backendCrop.ml_suitability_score <= 100
                      ? backendCrop.ml_suitability_score
                      : null;

                  const statusBadge =
                    verifiedClassification === 'recomendado'
                      ? { text: 'Recomendado (4/4)', bg: 'bg-[#159447]/15 text-[#159447] border-[#159447]/30' }
                      : verifiedClassification === 'condicionado'
                      ? { text: 'Condicionado (3/4)', bg: 'bg-[#E9A11B]/15 text-[#E9A11B] border-[#E9A11B]/30' }
                      : { text: `No recomendado (${backendCrop?.variables_ok ?? 0}/4)`, bg: 'bg-[#E34545]/15 text-[#E34545] border-[#E34545]/30' };

                  return (
                    <article
                      key={crop.id}
                      className="bg-white border border-[#D5D5D5] rounded-2xl p-5 shadow-xs flex flex-col justify-between space-y-4"
                    >
                      <div>
                        <div className="flex items-start justify-between gap-2 pb-3 border-b border-[#EEEEEE]">
                          <div>
                            <div className="flex items-center gap-2">
                              <h3 className="text-base font-bold text-[#202020]">{crop.common_name_es}</h3>
                              <span className="text-[11px] font-semibold bg-[#F4F4F4] text-[#555555] px-2 py-0.5 rounded-md border border-[#E0E0E0]">
                                {crop.category}
                              </span>
                              {crop.dataset_label && (
                                <span className="text-[10px] font-mono bg-[#1E1E1E] text-white px-2 py-0.5 rounded">
                                  {crop.dataset_label}
                                </span>
                              )}
                            </div>
                            <span className="text-xs italic text-[#777777] block mt-0.5">{crop.scientific_name}</span>
                          </div>
                          <span className={`text-[11px] font-bold px-2.5 py-1 rounded-lg border shrink-0 ${hasIncompleteEvaluation ? "bg-amber-50 text-amber-800 border-amber-300" : statusBadge.bg}`}>
                            {hasIncompleteEvaluation ? 'EvaluaciÃ³n incompleta' : statusBadge.text}
                          </span>
                        </div>

                        <div className="mt-3 space-y-2">
                          <div className="flex items-center justify-between text-xs">
                            <span className="font-semibold text-[#555555]">Compatibilidad estimada:</span>
                            <span className="font-bold text-[#202020] tabular-nums">{verifiedScore === null ? 'Sin puntuaciÃ³n verificada' : verifiedScore + '%'}</span>
                          </div>
                          <div className="w-full h-2 bg-[#EEEEEE] rounded-full overflow-hidden">
                            <div
                              className="h-full transition-all duration-300 rounded-full"
                              style={{
                                width: verifiedScore === null ? "0%" : `${verifiedScore}%`,
                                backgroundColor: verifiedClassification === 'recomendado'
                                    ? '#159447'
                                    : classification === 'condicionado'
                                    ? '#F39200'
                                    : '#E34545',
                              }}
                            />
                          </div>

                          <div className="grid grid-cols-2 gap-2 pt-1 text-[11px] text-[#555555]">
                            <div className="bg-[#F8F8F8] border border-[#EAEAEA] rounded-lg px-2.5 py-1.5">
                              Ciclo: <strong className="text-[#202020]">{crop.cycle_days_min}â€“{crop.cycle_days_max} dÃ­as</strong>
                            </div>
                            <div className="bg-[#F8F8F8] border border-[#EAEAEA] rounded-lg px-2.5 py-1.5">
                              RaÃ­z: <strong className="text-[#202020]">{crop.root_depth_m_min}â€“{crop.root_depth_m_max} m (p={crop.depletion_fraction_p})</strong>
                            </div>
                          </div>
                        </div>

                        <div className="grid grid-cols-2 gap-2 mt-3">
                          {checks.map((chk) => {
                            const backendCheck = backendCrop?.checks.find(
                              (item) => item.variable === chk.variable
                            );

                            const hasMeasurement = isVerifiedMeasurement(backendCheck);

                            const displayValue = hasMeasurement
                              ? backendCheck?.measured?.toFixed(2) ?? 'Sin mediciÃ³n'
                              : 'Sin mediciÃ³n';

                            const displayStatus = hasMeasurement
                              ? (backendCheck?.status ?? 'not_evaluated')
                              : 'not_evaluated';

                            return (
                              <div
                                key={chk.variable}
                                className="bg-[#F8F8F8] border border-[#EAEAEA] rounded-lg p-2 text-[11px] flex flex-col justify-between"
                              >
                                <div className="flex items-center justify-between text-[#777777]">
                                  <span>{chk.label}</span>
                                  <span
                                    className={`w-2 h-2 rounded-full ${
                                      displayStatus === 'not_evaluated'
                                        ? 'bg-[#A3A3A3]'
                                        : displayStatus === 'in_range'
                                        ? 'bg-[#159447]'
                                        : 'bg-[#E34545]'
                                    }`}
                                  />
                                </div>
                                <div className="flex items-baseline justify-between mt-1">
                                  <strong className="text-xs text-[#202020] tabular-nums">
                                    {displayValue}
                                  </strong>
                                  <span className="text-[10px] text-[#777777]">
                                    Ideal: {chk.range}
                                  </span>
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      </div>

                      <div>                        <button
                          onClick={() => setExpandedCropId(isExpanded ? null : crop.id)}
                          className="w-full py-2 px-3 rounded-xl bg-[#F4F4F4] hover:bg-[#E8E8E8] border border-[#DEDEDE] flex items-center justify-between text-xs font-semibold text-[#202020] cursor-pointer"
                        >
                          <span>Ver diagnÃ³stico por variable y notas</span>
                          {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                        </button>

                        {isExpanded && (
                          <div className="mt-3 pt-3 border-t border-[#EEEEEE] space-y-2 text-xs">
                            <p className="text-[#555555] bg-[#F8F8F8] p-2.5 rounded-xl border border-[#EAEAEA]">
                              <strong>Nota de cosecha:</strong> {crop.harvest_notes}
                            </p>
                            {checks.map((chk) => {
                              const backendCheck = backendCrop?.checks.find(
                                (item) => item.variable === chk.variable
                              );

                              const hasRealMeasurement = isVerifiedMeasurement(backendCheck);

                              const statusText = !hasRealMeasurement
                                ? 'Pendiente de mediciÃ³n'
                                : backendCheck?.status === 'in_range'
                                ? 'En rango'
                                : backendCheck?.status === 'below'
                                ? 'Bajo'
                                : backendCheck?.status === 'above'
                                ? 'Alto'
                                : 'Estado no disponible';

                              const sourceText = hasRealMeasurement
                                ? backendCheck?.origin ?? 'Fuente no especificada'
                                : 'Sin datos reales';

                              return (
                                <div key={chk.variable} className="bg-[#F8F8F8] rounded-xl p-2.5 border border-[#EAEAEA]">
                                  <div className="flex items-center justify-between font-semibold">
                                    <span>{chk.label} ({sourceText})</span>
                                    <span className={
                                      !hasRealMeasurement
                                        ? 'text-[#777777]'
                                        : backendCheck?.status === 'in_range'
                                        ? 'text-[#159447]'
                                        : 'text-[#E34545]'
                                    }>
                                      {statusText}
                                    </span>
                                  </div>
                                  {hasRealMeasurement && backendCheck?.advice_template && (
                                    <p className="text-[11px] text-[#555555] mt-1">
                                      {backendCheck?.advice_template}
                                    </p>
                                  )}
                                </div>
                              );
                            })}
                          </div>
                        )}
                      </div>
                    </article>
                  );
                })}

                {filteredCrops.length === 0 && (
                  <div className="md:col-span-2 bg-white border border-[#D5D5D5] rounded-2xl p-8 text-center">
                    <Sprout className="w-10 h-10 text-[#159447] mx-auto mb-3" />
                    <h3 className="text-base font-bold text-[#202020]">
                      No hay cultivos evaluados en esta categorÃ­a
                    </h3>
                    <p className="text-sm text-[#777777] mt-2 max-w-md mx-auto">
                      TodavÃ­a faltan mediciones reales del suelo para completar
                      las recomendaciones agrÃ­colas.
                    </p>
                    <button
                      type="button"
                      onClick={() => {
                        setCropFilterClass('all');
                        setCropSearch('');
                      }}
                      className="mt-4 px-4 py-2 bg-[#1E1E1E] text-white rounded-xl text-xs font-semibold hover:bg-[#333333]"
                    >
                      Ver todos los cultivos
                    </button>
                  </div>
                )}
              </div>
            </section>
          )}



          {/* ==================================================================
              VISTA 4: ESTADO DE LOS SENSORES (COMPLETA)
             ================================================================== */}
          {activeTab === 'sensors' && (
            <section className="space-y-4">
              <div className="bg-white border border-[#D5D5D5] rounded-2xl p-6 flex flex-wrap items-center justify-between gap-4">
                <div>
                  <h2 className="text-xl font-bold text-[#202020]">Estado de los sensores</h2>
                  <p className="text-xs text-[#777777] mt-0.5">
                    Dispositivo {deviceUid} Â· Canal seleccionado:{' '}
                    <strong>Wi-Fi</strong>
                    {lastTelemetryAt && (
                      <span className="block mt-1">Ãšltima lectura: {new Date(lastTelemetryAt).toLocaleString('es-MX')}</span>
                    )}
                    {telemetryError && (
                      <span className="block mt-1 text-red-600">{telemetryError}</span>
                    )}
                  </p>
                </div>
                <span
                  className={`inline-flex items-center gap-2 text-xs font-bold px-3 py-1.5 rounded-full ${
                    espConnected ? 'text-[#F39200] bg-[#F39200]/10' : 'text-[#E34545] bg-[#E34545]/10'
                  }`}
                >
                  <ShieldCheck className="w-4 h-4" />
                  {espConnected ? 'ESP32 conectado Â· datos reales' : 'ESP32 sin conexiÃ³n reciente'}
                </span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {[
                  {
                    name: 'Sensor de Temperatura (DS18B20)',
                    reading: espConnected ? `${latest.soil_temperature_c.toFixed(2)} Â°C` : 'Sin lectura reciente',
                    comm: 'ESP32 Â· DS18B20 Â· Wi-Fi',
                    sourceStatus: espConnected ? 'real' : 'pending',
                  },
                  {
                    name: 'Sensor de Humedad Resistivo',
                    reading: espConnected ? `${latest.soil_moisture_pct.toFixed(1)} % Â· ADC recibido` : 'Sin lectura reciente',
                    comm: 'ESP32 Â· ADC GPIO34 Â· Wi-Fi',
                    sourceStatus: espConnected ? 'real' : 'pending',
                  },
                  {
                    name: 'MÃ³dulo de Nivel de pH (Simulado)',
                    reading: `${latest.soil_ph.toFixed(2)} pH (simulado)`,
                    comm: 'Dato de demostraciÃ³n Â· No validado',
                    sourceStatus: 'simulated',
                  },
                  {
                    name: 'Canal de PrecipitaciÃ³n (NASA POWER)',
                    reading: climateSummary?.rainfall_30d?.precip_total_mm != null
                      ? `${climateSummary.rainfall_30d.precip_total_mm.toFixed(2)} mm (30 dÃ­as)`
                      : 'Sin datos disponibles',
                    comm: 'Fuente satelital Â· NASA POWER',
                    sourceStatus: climateSummary?.rainfall_30d?.precip_total_mm != null
                      ? 'real'
                      : 'pending',
                  },
                ].map((s, idx) => (
                  <div key={idx} className="bg-white border border-[#D5D5D5] rounded-2xl p-5 flex items-start justify-between gap-4">
                    <div>
                      <div className="flex items-center gap-2 mb-1">
                        <span className={`w-2.5 h-2.5 rounded-full ${s.sourceStatus === 'real' ? 'bg-[#159447]' : s.sourceStatus === 'simulated' ? 'bg-[#F39200]' : 'bg-[#E34545]'}`} />
                        <h3 className="text-sm font-bold text-[#202020]">{s.name}</h3>
                      </div>
                      <p className="text-xs text-[#777777] mb-3">{s.comm}</p>
                      <span className="text-xs font-semibold text-[#202020] bg-[#F8F8F8] border border-[#E5E5E5] px-2.5 py-1 rounded-lg">
                        Ãšltima lectura: {s.reading} ({latest.timeLabel})
                      </span>
                    </div>
                    <Radio className={`w-5 h-5 shrink-0 ${s.sourceStatus === 'real' ? 'text-[#159447]' : s.sourceStatus === 'simulated' ? 'text-[#F39200]' : 'text-[#E34545]'}`} />
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* ==================================================================
              VISTA 5: RECOMENDACIONES (COMPLETA CON LAS 4 VARIABLES DE ADVICE_RULES)
             ================================================================== */}
          {activeTab === 'advice' && (
            <section className="space-y-4">
              <div className="bg-white border border-[#D5D5D5] rounded-2xl p-6">
                <h2 className="text-xl font-bold text-[#202020]">Recomendaciones para cuidar el suelo</h2>
                <p className="text-xs text-[#777777] mt-0.5">
                  DiagnÃ³stico agronÃ³mico generado en tiempo real con las reglas de advice_rules (PostgreSQL v3.3).
                </p>
              </div>

              <div className="space-y-3">
                {(() => {
                  const items: { priority: 'Alta' | 'Media' | 'Baja'; title: string; detail: string; metric: string }[] = [];
                  const moistTarget = computeFao56MoistureRange(0.5, soilTexture);

                  // 1. Humedad
                  if (latest.soil_moisture_pct < moistTarget.minPct) {
                    items.push({
                      priority: 'Alta',
                      title: 'Aplicar riego de apoyo en la parcela',
                      detail: formatAdviceRule('soil_moisture', 'below', latest.soil_moisture_pct, moistTarget.minPct),
                      metric: `Humedad: ${latest.soil_moisture_pct.toFixed(1)}%`,
                    });
                  } else if (latest.soil_moisture_pct > moistTarget.maxPct) {
                    items.push({
                      priority: 'Alta',
                      title: 'Suspender riego y supervisar drenaje',
                      detail: formatAdviceRule('soil_moisture', 'above', latest.soil_moisture_pct, moistTarget.maxPct),
                      metric: `Humedad: ${latest.soil_moisture_pct.toFixed(1)}%`,
                    });
                  } else {
                    items.push({
                      priority: 'Baja',
                      title: 'Humedad volumÃ©trica en rango Ã³ptimo (FAO-56)',
                      detail: `El suelo registra ${latest.soil_moisture_pct.toFixed(1)}%, dentro del rango ideal (${moistTarget.minPct}%â€“${moistTarget.maxPct}%) para tierra ${SOIL_TEXTURES[soilTexture].name_es}.`,
                      metric: `Humedad: ${latest.soil_moisture_pct.toFixed(1)}%`,
                    });
                  }

                  // 2. Temperatura
                  if (latest.soil_temperature_c < 18) {
                    items.push({
                      priority: 'Media',
                      title: 'Proteger suelo ante baja temperatura',
                      detail: formatAdviceRule('soil_temperature', 'below', latest.soil_temperature_c, 18),
                      metric: `Temp: ${latest.soil_temperature_c.toFixed(1)} Â°C`,
                    });
                  } else if (latest.soil_temperature_c > 30) {
                    items.push({
                      priority: 'Media',
                      title: 'Mitigar temperatura alta en raÃ­z',
                      detail: formatAdviceRule('soil_temperature', 'above', latest.soil_temperature_c, 28),
                      metric: `Temp: ${latest.soil_temperature_c.toFixed(1)} Â°C`,
                    });
                  } else {
                    items.push({
                      priority: 'Baja',
                      title: 'Temperatura de raÃ­z favorable para germinaciÃ³n',
                      detail: `Lectura tÃ©rmica estable en ${latest.soil_temperature_c.toFixed(1)} Â°C, adecuada para el desarrollo radicular.`,
                      metric: `Temp: ${latest.soil_temperature_c.toFixed(1)} Â°C`,
                    });
                  }

                  // 3. pH Simulado
                  if (latest.soil_ph < 5.8) {
                    items.push({
                      priority: 'Media',
                      title: 'Corregir acidez del suelo (pH simulado)',
                      detail: formatAdviceRule('soil_ph', 'below', latest.soil_ph, 6.2),
                      metric: `pH: ${latest.soil_ph.toFixed(2)}`,
                    });
                  } else if (latest.soil_ph > 7.2) {
                    items.push({
                      priority: 'Media',
                      title: 'Reducir alcalinidad del suelo (pH simulado)',
                      detail: formatAdviceRule('soil_ph', 'above', latest.soil_ph, 6.8),
                      metric: `pH: ${latest.soil_ph.toFixed(2)}`,
                    });
                  } else {
                    items.push({
                      priority: 'Baja',
                      title: 'Nivel de pH simulado en equilibrio quÃ­mico',
                      detail: `Con un pH de ${latest.soil_ph.toFixed(2)}, la disponibilidad de nutrientes en la soluciÃ³n del suelo es Ã³ptima.`,
                      metric: `pH: ${latest.soil_ph.toFixed(2)}`,
                    });
                  }

                  // 4. PrecipitaciÃ³n
                  if (latest.precip_total_mm < 45) {
                    items.push({
                      priority: 'Media',
                      title: 'Compensar baja precipitaciÃ³n acumulada',
                      detail: formatAdviceRule('rainfall', 'below', latest.precip_total_mm, 60),
                      metric: `Lluvia 30d: ${latest.precip_total_mm.toFixed(1)} mm`,
                    });
                  } else if (latest.precip_total_mm > 140) {
                    items.push({
                      priority: 'Alta',
                      title: 'Prevenir saturaciÃ³n por exceso de lluvia',
                      detail: formatAdviceRule('rainfall', 'above', latest.precip_total_mm, 110),
                      metric: `Lluvia 30d: ${latest.precip_total_mm.toFixed(1)} mm`,
                    });
                  } else {
                    items.push({
                      priority: 'Baja',
                      title: 'Acumulado pluvial de 30 dÃ­as en rango normal',
                      detail: `La celda climÃ¡tica NASA POWER reporta ${latest.precip_total_mm.toFixed(1)} mm acumulados, favorable para el ciclo actual.`,
                      metric: `Lluvia 30d: ${latest.precip_total_mm.toFixed(1)} mm`,
                    });
                  }

                  return items.map((rec, i) => (
                    <div key={i} className="bg-white border border-[#D5D5D5] rounded-2xl p-5 flex items-start justify-between gap-4">
                      <div>
                        <div className="flex items-center gap-2 mb-1.5">
                          <span
                            className={`text-[11px] font-bold px-2.5 py-0.5 rounded-full ${
                              rec.priority === 'Alta'
                                ? 'bg-[#E34545]/15 text-[#E34545]'
                                : rec.priority === 'Media'
                                ? 'bg-[#E9A11B]/15 text-[#E9A11B]'
                                : 'bg-[#159447]/15 text-[#159447]'
                            }`}
                          >
                            Prioridad {rec.priority}
                          </span>
                          <span className="text-xs font-semibold text-[#777777]">{rec.metric}</span>
                        </div>
                        <h3 className="text-sm font-bold text-[#202020] mb-1">{rec.title}</h3>
                        <p className="text-xs text-[#555555] leading-relaxed">{rec.detail}</p>
                      </div>
                      {rec.priority === 'Baja' ? (
                        <CheckCircle2 className="w-5 h-5 text-[#159447] shrink-0" />
                      ) : (
                        <AlertTriangle className="w-5 h-5 text-[#F39200] shrink-0" />
                      )}
                    </div>
                  ));
                })()}
              </div>
            </section>
          )}
        </main>
      </div>

      {/* BURBUJA FLOTANTE DEL AGENTE IA */}
      <AgroAssistantBubble latest={latest} texture={soilTexture} />
    </div>
  );
}

export default App;




































