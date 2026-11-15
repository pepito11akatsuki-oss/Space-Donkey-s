import React, { useState, useEffect, useMemo, useRef } from 'react';
import {
  Home,
  Activity,
  Sprout,
  Cpu,
  ClipboardCheck,
  Play,
  Pause,
  Settings,
  CheckCircle2,
  AlertTriangle,
  XCircle,
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
} from 'lucide-react';

// ============================================================================
// 1. TIPOS EXACTOS DEL ESQUEMA POSTGRESQL v3.3 (agrostake_v3_3_completo.sql)
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
  image: string;
}

interface TelemetryPoint {
  timeLabel: string;
  measured_at: string;
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
// 2. SEMILLAS OFICIALES DE TU ARCHIVO SQL (FAO-56 + 6 CULTIVOS + ADVICE_RULES)
// ============================================================================
const SOIL_TEXTURES: Record<SoilTextureCode, SoilWaterCharacteristic> = {
  sand: { texture_code: 'sand', name_es: 'Arena', fc_min: 0.07, fc_max: 0.17, wp_min: 0.02, wp_max: 0.07 },
  loamy_sand: { texture_code: 'loamy_sand', name_es: 'Arena franca', fc_min: 0.11, fc_max: 0.19, wp_min: 0.03, wp_max: 0.10 },
  sandy_loam: { texture_code: 'sandy_loam', name_es: 'Franco arenoso', fc_min: 0.18, fc_max: 0.28, wp_min: 0.06, wp_max: 0.16 },
  loam: { texture_code: 'loam', name_es: 'Franco (Estándar)', fc_min: 0.20, fc_max: 0.30, wp_min: 0.07, wp_max: 0.17 },
  silt_loam: { texture_code: 'silt_loam', name_es: 'Franco limoso', fc_min: 0.22, fc_max: 0.36, wp_min: 0.09, wp_max: 0.21 },
  clay: { texture_code: 'clay', name_es: 'Arcilla', fc_min: 0.32, fc_max: 0.40, wp_min: 0.20, wp_max: 0.24 },
};

// Vista SQL v_crop_moisture_range (FAO-56 Tabla 19 y 22)
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
    common_name_es: 'Maíz',
    scientific_name: 'Zea mays',
    dataset_label: 'maize',
    category: 'Cereal',
    cycle_days_min: 100,
    cycle_days_max: 140,
    harvest_notes: 'Cosecha con grano en madurez fisiológica.',
    depletion_fraction_p: 0.55,
    root_depth_m_min: 1.0,
    root_depth_m_max: 1.7,
    temp_min: 18.0,
    temp_max: 30.0,
    ph_min: 5.8,
    ph_max: 7.0,
    rain_min: 50.0,
    rain_max: 120.0,
    image: 'https://images.unsplash.com/photo-1551754655-cd27e38d2076?auto=format&fit=crop&w=600&q=80',
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
    image: 'https://images.unsplash.com/photo-1551462147-ff29053bfc14?auto=format&fit=crop&w=600&q=80',
  },
  {
    id: 3,
    common_name_es: 'Tomate',
    scientific_name: 'Solanum lycopersicum',
    dataset_label: null,
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
    image: 'https://images.unsplash.com/photo-1592924357228-91a4daadcfea?auto=format&fit=crop&w=600&q=80',
  },
  {
    id: 4,
    common_name_es: 'Sorgo',
    scientific_name: 'Sorghum bicolor',
    dataset_label: null,
    category: 'Cereal',
    cycle_days_min: 100,
    cycle_days_max: 130,
    harvest_notes: 'Tolerante a sequía.',
    depletion_fraction_p: 0.55,
    root_depth_m_min: 1.0,
    root_depth_m_max: 2.0,
    temp_min: 20.0,
    temp_max: 32.0,
    ph_min: 5.5,
    ph_max: 7.5,
    rain_min: 40.0,
    rain_max: 100.0,
    image: 'https://images.unsplash.com/photo-1500382017468-9049fed747ef?auto=format&fit=crop&w=600&q=80',
  },
  {
    id: 5,
    common_name_es: 'Trigo',
    scientific_name: 'Triticum aestivum',
    dataset_label: null,
    category: 'Cereal',
    cycle_days_min: 110,
    cycle_days_max: 150,
    harvest_notes: 'Cultivo de clima templado/frío.',
    depletion_fraction_p: 0.55,
    root_depth_m_min: 1.5,
    root_depth_m_max: 1.8,
    temp_min: 10.0,
    temp_max: 24.0,
    ph_min: 6.0,
    ph_max: 7.5,
    rain_min: 40.0,
    rain_max: 90.0,
    image: 'https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?auto=format&fit=crop&w=600&q=80',
  },
  {
    id: 6,
    common_name_es: 'Arroz',
    scientific_name: 'Oryza sativa',
    dataset_label: 'rice',
    category: 'Cereal',
    cycle_days_min: 105,
    cycle_days_max: 150,
    harvest_notes: 'Requiere lámina de agua; sensible a sequía.',
    depletion_fraction_p: 0.20,
    root_depth_m_min: 0.5,
    root_depth_m_max: 1.0,
    temp_min: 20.0,
    temp_max: 32.0,
    ph_min: 5.5,
    ph_max: 7.0,
    rain_min: 120.0,
    rain_max: 300.0,
    image: 'https://images.unsplash.com/photo-1536304993881-ff6e9eefa2a6?auto=format&fit=crop&w=600&q=80',
  },
];

// Tabla SQL advice_rules (Secciones 11 y 18 del script SQL)
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
    return `Temperatura del suelo baja (${c} °C): conviene retrasar la siembra o usar acolchado para acercarse a ${t} °C.`;
  }
  if (variable === 'soil_temperature' && status === 'above') {
    return `Temperatura del suelo alta (${c} °C): conviene usar acolchado y riegos ligeros para bajar hacia ${t} °C.`;
  }
  if (variable === 'soil_ph' && status === 'below') {
    return `pH del suelo bajo, suelo ácido (${current.toFixed(2)}): considerar encalado agrícola para subir hacia ${target.toFixed(1)}.`;
  }
  if (variable === 'soil_ph' && status === 'above') {
    return `pH del suelo alto, suelo alcalino (${current.toFixed(2)}): considerar materia orgánica o azufre elemental para bajar hacia ${target.toFixed(1)}.`;
  }
  if (variable === 'rainfall' && status === 'below') {
    return `Lluvia acumulada baja (${c} mm): programar riego complementario para aproximarse a ${t} mm.`;
  }
  return `Lluvia acumulada alta (${c} mm): vigilar encharcamiento y mejorar el drenaje; el objetivo es cerca de ${t} mm.`;
}

// Cálculo gradual soft-boundary (0 a 100) para ml_suitability_score
function calcSoftVariableScore(val: number, min: number, max: number, tolerance: number): number {
  if (val >= min && val <= max) return 100;
  const dist = val < min ? min - val : val - max;
  return Math.max(0, Math.round((1 - dist / tolerance) * 100));
}

// ============================================================================
// 3. COMPONENTE MINIATURA DE BATERÍA (ESQUINA SUPERIOR DERECHA)
// ============================================================================
const MinimalBatteryStatus: React.FC<{ batteryV: number }> = ({ batteryV }) => {
  // Convierte voltaje LiPo (3.3V - 4.2V) a porcentaje 0-100%
  const pct = Math.min(100, Math.max(5, Math.round(((batteryV - 3.3) / (4.2 - 3.3)) * 100)));
  const barColor = pct > 35 ? '#159447' : pct > 15 ? '#E9A11B' : '#E34545';

  return (
    <div
      className="inline-flex items-center gap-2 bg-[#F8F8F8] border border-[#D5D5D5] px-2.5 py-1.5 rounded-lg"
      title={`Batería de la estaca: ${pct}% (${batteryV.toFixed(2)} V)`}
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
// 4. ILUSTRACIÓN LIMPIA DE LA ESTACA (CON SOPORTE PARA image_015581.jpg)
// ============================================================================
const StakePhotoDisplay: React.FC = () => {
  const [imgError, setImgError] = useState(false);

  return (
    <div className="relative w-full h-72 md:h-80 bg-[#F8F8F8] border border-[#DEDEDE] rounded-2xl overflow-hidden flex items-center justify-center p-4">
      {!imgError ? (
        <img
          src="/image_015581.jpg"
          alt="Estaca AgroStake"
          onError={() => setImgError(true)}
          className="w-full h-full object-contain rounded-xl"
        />
      ) : (
        <svg viewBox="0 0 260 320" className="w-48 h-64">
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
          {/* 3 Varillas inferiores */}
          <rect x="103" y="195" width="6" height="92" rx="3" fill="url(#inoxRod)" />
          <rect x="127" y="202" width="6" height="96" rx="3" fill="url(#inoxRod)" />
          <rect x="151" y="195" width="6" height="92" rx="3" fill="url(#inoxRod)" />
          {/* Cuerpo cilíndrico blanco con coples */}
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
        'Hola. Soy el asistente agrícola de AgroStake. Estoy conectado a los datos actuales de tu tierra. ¿Tienes dudas sobre qué sembrar, cómo regar o qué significan tus lecturas?',
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
      const best = evaluated.filter((e) => e.okCount >= 3).map((e) => `${e.crop.common_name_es} (${e.okCount}/4 condiciones)`);
      if (best.length > 0) {
        return `Según las lecturas actuales (${latest.soil_temperature_c.toFixed(1)} °C, ${latest.soil_moisture_pct.toFixed(1)}% de humedad, pH ${latest.soil_ph.toFixed(2)} y ${latest.precip_total_mm.toFixed(1)} mm de lluvia), las mejores opciones para tu terreno son: ${best.join(', ')}.`;
      }
      return `En este momento el cultivo más cercano es ${evaluated[0].crop.common_name_es} (${evaluated[0].okCount}/4 variables en rango). Te sugiero revisar el apartado de Recomendaciones para ajustar la humedad antes de sembrar.`;
    }

    if (q.includes('humedad') || q.includes('regar') || q.includes('riego') || q.includes('agua')) {
      const refRange = computeFao56MoistureRange(0.5, texture);
      if (latest.soil_moisture_pct < refRange.minPct) {
        return formatAdviceRule('soil_moisture', 'below', latest.soil_moisture_pct, refRange.minPct);
      }
      if (latest.soil_moisture_pct > refRange.maxPct) {
        return formatAdviceRule('soil_moisture', 'above', latest.soil_moisture_pct, refRange.maxPct);
      }
      return `La humedad actual es de ${latest.soil_moisture_pct.toFixed(1)}%, lo cual está dentro del rango saludable (${refRange.minPct}% a ${refRange.maxPct}%) para suelo ${SOIL_TEXTURES[texture].name_es}. No necesitas regar de inmediato.`;
    }

    if (q.includes('ph') || q.includes('acidez') || q.includes('cal')) {
      if (latest.soil_ph < 5.8) {
        return formatAdviceRule('soil_ph', 'below', latest.soil_ph, 6.2);
      }
      if (latest.soil_ph > 7.2) {
        return formatAdviceRule('soil_ph', 'above', latest.soil_ph, 6.8);
      }
      return `El pH del suelo está en ${latest.soil_ph.toFixed(2)}. Es un nivel equilibrado que permite que las plantas aprovechen bien los nutrientes de la tierra.`;
    }

    if (q.includes('temperatura') || q.includes('calor') || q.includes('frio')) {
      return `La temperatura bajo tierra es de ${latest.soil_temperature_c.toFixed(1)} °C. La mayoría de los granos y hortalizas germinan bien entre 18 °C y 28 °C.`;
    }

    return `Resumen actual de tu parcela: Temperatura ${latest.soil_temperature_c.toFixed(1)} °C, Humedad ${latest.soil_moisture_pct.toFixed(1)}%, pH ${latest.soil_ph.toFixed(2)} y Lluvia acumulada de ${latest.precip_total_mm.toFixed(1)} mm. Pregúntame por un cultivo específico o si necesitas regar.`;
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
      // Intenta conectar con el backend de IA de tu compañero si está activo en localhost:8000
      const ctrl = new AbortController();
      const timer = setTimeout(() => ctrl.abort(), 2500);
      const res = await fetch('http://localhost:8000/api/agent/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: cleanText,
          soil_temperature_c: latest.soil_temperature_c,
          soil_moisture_pct: latest.soil_moisture_pct,
          soil_ph: latest.soil_ph,
          precip_total_mm: latest.precip_total_mm,
          soil_texture: texture,
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
      await new Promise((r) => setTimeout(r, 450));
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
          {/* Encabezado */}
          <div className="bg-[#1E1E1E] text-white px-4 py-3 flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg bg-[#F39200] text-[#1E1E1E] flex items-center justify-center">
                <Bot className="w-4 h-4 stroke-[2.2]" />
              </div>
              <div>
                <h4 className="text-xs font-bold tracking-tight">Asistente Agrícola IA</h4>
                <span className="text-[11px] text-neutral-400 block">Conectado a base de datos v3.3</span>
              </div>
            </div>
            <button
              onClick={() => setIsOpen(false)}
              className="w-7 h-7 rounded-lg bg-neutral-800 hover:bg-neutral-700 flex items-center justify-center text-neutral-300"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* Resumen rápido de lecturas */}
          <div className="bg-[#F8F8F8] border-b border-[#E5E5E5] px-3 py-1.5 flex justify-between text-[11px] text-[#555555]">
            <span>Temp: <strong className="text-[#202020]">{latest.soil_temperature_c.toFixed(1)}°C</strong></span>
            <span>Hum: <strong className="text-[#202020]">{latest.soil_moisture_pct.toFixed(1)}%</strong></span>
            <span>pH: <strong className="text-[#202020]">{latest.soil_ph.toFixed(2)}</strong></span>
            <span>Lluvia: <strong className="text-[#202020]">{latest.precip_total_mm.toFixed(0)}mm</strong></span>
          </div>

          {/* Lista de mensajes */}
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
                <span>Consultando datos del terreno...</span>
              </div>
            )}
            <div ref={endRef} />
          </div>

          {/* Preguntas sugeridas */}
          <div className="px-3 py-1.5 bg-white border-t border-[#EEEEEE] flex gap-1.5 overflow-x-auto">
            {['¿Qué puedo sembrar?', '¿Necesito regar?', 'Estado del pH'].map((q) => (
              <button
                key={q}
                type="button"
                onClick={() => sendMessage(q)}
                className="shrink-0 text-[11px] bg-[#F4F4F4] hover:bg-[#1E1E1E] hover:text-white text-[#202020] px-2.5 py-1 rounded-md border border-[#DEDEDE] transition-colors"
              >
                {q}
              </button>
            ))}
          </div>

          {/* Input */}
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
              placeholder="Pregunta sobre tus cultivos o suelo..."
              className="flex-1 bg-[#F8F8F8] border border-[#D5D5D5] rounded-xl px-3 py-2 text-xs text-[#202020] focus:outline-none focus:border-[#1E1E1E]"
            />
            <button
              type="submit"
              disabled={!input.trim() || isTyping}
              className="w-9 h-9 rounded-xl bg-[#F39200] hover:bg-[#e08600] disabled:opacity-40 text-[#1E1E1E] flex items-center justify-center transition-colors"
            >
              <Send className="w-4 h-4" />
            </button>
          </form>
        </div>
      )}

      {/* Botón burbuja estilo Messenger */}
      <button
        onClick={() => setIsOpen((o) => !o)}
        className="flex items-center gap-2.5 h-12 px-4 rounded-full bg-[#1E1E1E] hover:bg-black text-white shadow-lg border border-[#333333] transition-all"
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
// 6. APLICACIÓN PRINCIPAL AGROSTAKE (ACOPLADA A SQL v3.3)
// ============================================================================
export function App() {
  // --- Autenticación y Registro (acoplado a auth_register_owner y auth_get_user_by_email) ---
  const [user, setUser] = useState<AuthUser | null>(null);
  const [authMode, setAuthMode] = useState<'login' | 'register'>('login');
  const [loginEmail, setLoginEmail] = useState('productor@agrostake.mx');
  const [loginPass, setLoginPass] = useState('123456');
  const [authError, setAuthError] = useState('');

  // Campos de Registro
  const [regFirstName, setRegFirstName] = useState('');
  const [regLastName, setRegLastName] = useState('');
  const [regEmail, setRegEmail] = useState('');
  const [regPhone, setRegPhone] = useState('');
  const [regPassword, setRegPassword] = useState('');
  const [regConfirmPass, setRegConfirmPass] = useState('');

  // --- Navegación por Iconos Separados ---
  const [activeTab, setActiveTab] = useState<'home' | 'telemetry' | 'crops' | 'sensors' | 'advice'>('home');
  const [expandedCropId, setExpandedCropId] = useState<number | null>(1);

  // --- Animación "Iniciar análisis" en Inicio ---
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisStepText, setAnalysisStepText] = useState('');

  // --- Control de Tiempo Real y Pausa Automática al Configurar ---
  const [sampleIntervalSec, setSampleIntervalSec] = useState<number>(2);
  const [isConfiguringTime, setIsConfiguringTime] = useState<boolean>(false);
  const [soilTexture, setSoilTexture] = useState<SoilTextureCode>('loam');

  // --- Serie de Tiempo (soil_readings + latest_soil_ph + weather_daily) ---
  const [history, setHistory] = useState<TelemetryPoint[]>(() => {
    const now = Date.now();
    return Array.from({ length: 12 }, (_, idx) => {
      const t = new Date(now - (11 - idx) * 2000);
      return {
        timeLabel: t.toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
        measured_at: t.toISOString(),
        soil_temperature_c: Number((22.4 + Math.sin(idx * 0.5) * 0.8).toFixed(1)),
        soil_moisture_pct: Number((21.5 + Math.cos(idx * 0.4) * 1.4).toFixed(1)),
        soil_ph: Number((6.45 + Math.sin(idx * 0.3) * 0.06).toFixed(2)),
        precip_total_mm: 70.0, // Valor base en ventana de 30 días de tu test SQL
        battery_v: 4.04,
      };
    });
  });

  const latest = history[history.length - 1];

  // Actualización en tiempo real (se pausa automáticamente si isConfiguringTime === true)
  useEffect(() => {
    if (!user || isConfiguringTime) return;

    const timer = setInterval(() => {
      setHistory((prev) => {
        const last = prev[prev.length - 1];
        const now = new Date();
        const nextTemp = Math.min(35, Math.max(12, +(last.soil_temperature_c + (Math.random() - 0.48) * 0.4).toFixed(1)));
        const nextMoist = Math.min(42, Math.max(10, +(last.soil_moisture_pct + (Math.random() - 0.48) * 0.7).toFixed(1)));
        const nextPh = Math.min(7.8, Math.max(5.2, +(last.soil_ph + (Math.random() - 0.49) * 0.03).toFixed(2)));

        const nextPoint: TelemetryPoint = {
          timeLabel: now.toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
          measured_at: now.toISOString(),
          soil_temperature_c: nextTemp,
          soil_moisture_pct: nextMoist,
          soil_ph: nextPh,
          precip_total_mm: last.precip_total_mm,
          battery_v: Math.max(3.65, +(last.battery_v - 0.0005).toFixed(2)),
        };
        return [...prev.slice(-19), nextPoint];
      });
    }, sampleIntervalSec * 1000);

    return () => clearInterval(timer);
  }, [user, sampleIntervalSec, isConfiguringTime]);

  // --- Validación de Login y Registro ---
  const handleLoginSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setAuthError('');
    if (!loginEmail.includes('@')) {
      setAuthError('Ingresa un correo electrónico válido.');
      return;
    }
    if (loginPass.trim().length < 4) {
      setAuthError('La contraseña debe tener al menos 4 caracteres.');
      return;
    }

    setUser({
      id: 'd290f1ee-6c54-4b01-90e6-d701748f0851',
      org_id: 'a100f1ee-6c54-4b01-90e6-d701748f0111',
      org_name: 'Parcela AgroStake',
      email: loginEmail.trim().toLowerCase(),
      full_name: loginEmail.split('@')[0],
      phone: '8441234567',
      role: 'owner',
    });
  };

  const handleRegisterSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setAuthError('');

    if (regFirstName.trim().length < 2) {
      setAuthError('Ingresa tu nombre.');
      return;
    }
    if (regLastName.trim().length < 2) {
      setAuthError('Ingresa tu apellido.');
      return;
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(regEmail.trim())) {
      setAuthError('Ingresa un correo electrónico válido.');
      return;
    }
    const cleanPhone = regPhone.replace(/\D/g, '');
    if (cleanPhone.length !== 10) {
      setAuthError('El número telefónico debe tener exactamente 10 dígitos.');
      return;
    }
    if (regPassword.length < 6) {
      setAuthError('La contraseña debe tener mínimo 6 caracteres.');
      return;
    }
    if (regPassword !== regConfirmPass) {
      setAuthError('Las contraseñas no coinciden.');
      return;
    }

    const fullName = `${regFirstName.trim()} ${regLastName.trim()}`;
    setUser({
      id: crypto.randomUUID ? crypto.randomUUID() : 'user-uuid-01',
      org_id: crypto.randomUUID ? crypto.randomUUID() : 'org-uuid-01',
      org_name: `Rancho ${regLastName.trim()}`,
      email: regEmail.trim().toLowerCase(),
      full_name: fullName,
      phone: cleanPhone,
      role: 'owner',
    });
  };

  // --- Secuencia de "Iniciar análisis" desde la Casa hacia Valores en Vivo ---
  const triggerStartAnalysis = () => {
    if (isAnalyzing) return;
    setIsAnalyzing(true);
    const steps = [
      'Conectando con la estaca en tierra...',
      'Leyendo temperatura y humedad de la raíz...',
      'Verificando pH y lluvia acumulada (30 días)...',
      'Calculando compatibilidad de cultivos...',
    ];
    setAnalysisStepText(steps[0]);

    setTimeout(() => setAnalysisStepText(steps[1]), 650);
    setTimeout(() => setAnalysisStepText(steps[2]), 1300);
    setTimeout(() => setAnalysisStepText(steps[3]), 1950);
    setTimeout(() => {
      setIsAnalyzing(false);
      setAnalysisStepText('');
      setActiveTab('telemetry');
    }, 2500);
  };

  // --- Evaluación de los 6 Cultivos con las Reglas Estrictas del SQL v3.3 ---
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
        { variable: 'soil_temperature' as VariableCode, label: 'Temperatura', val: `${latest.soil_temperature_c.toFixed(1)} °C`, range: `${crop.temp_min}–${crop.temp_max} °C`, ...tempCheck },
        { variable: 'soil_moisture' as VariableCode, label: 'Humedad (FAO-56)', val: `${latest.soil_moisture_pct.toFixed(1)} %`, range: `${moistRange.minPct}–${moistRange.maxPct} %`, ...moistCheck },
        { variable: 'soil_ph' as VariableCode, label: 'Nivel de pH', val: `${latest.soil_ph.toFixed(2)} pH`, range: `${crop.ph_min}–${crop.ph_max} pH`, ...phCheck },
        { variable: 'rainfall' as VariableCode, label: 'Lluvia (30 días)', val: `${latest.precip_total_mm.toFixed(0)} mm`, range: `${crop.rain_min}–${crop.rain_max} mm`, ...rainCheck },
      ];

      const variables_ok = checks.filter((c) => c.status === 'in_range').length;

      // Clasificación oficial de la tabla recommendation_results en el SQL
      const classification: ViabilityClass =
        variables_ok === 4 ? 'recomendado' : variables_ok === 3 ? 'condicionado' : 'no_recomendado';

      // Porcentaje gradual (ml_suitability_score 0-100)
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

  // ============================================================================
  // PANTALLA DE ACCESO Y REGISTRO (FORMAL Y MINIMALISTA)
  // ============================================================================
  if (!user) {
    return (
      <div className="min-h-screen bg-[#EEEEEE] text-[#202020] flex items-center justify-center p-4 font-sans">
        <div className="w-full max-w-md bg-white border border-[#D5D5D5] rounded-2xl shadow-sm p-8">
          {/* Encabezado de marca */}
          <div className="flex items-center gap-3 mb-6">
            <div className="w-10 h-10 rounded-xl bg-[#1E1E1E] text-white flex items-center justify-center">
              <Sprout className="w-5 h-5 text-[#F39200]" />
            </div>
            <div>
              <h1 className="text-lg font-bold tracking-tight text-[#202020]">AgroStake</h1>
              <p className="text-xs text-[#777777]">Sistema de Monitoreo de Tierra</p>
            </div>
          </div>

          <h2 className="text-xl font-bold text-[#202020] mb-1">
            {authMode === 'login' ? 'Iniciar sesión' : 'Crear cuenta de productor'}
          </h2>
          <p className="text-xs text-[#777777] mb-6">
            {authMode === 'login'
              ? 'Ingresa tus datos para consultar el estado de tu terreno.'
              : 'Completa el formulario para registrar tu parcela en el sistema.'}
          </p>

          {authError && (
            <div className="mb-4 p-3 rounded-xl bg-[#E34545]/10 border border-[#E34545]/30 text-xs font-medium text-[#E34545]">
              {authError}
            </div>
          )}

          {authMode === 'login' ? (
            <form onSubmit={handleLoginSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-[#202020] mb-1.5">Correo electrónico</label>
                <input
                  type="email"
                  value={loginEmail}
                  onChange={(e) => setLoginEmail(e.target.value)}
                  className="w-full bg-[#F8F8F8] border border-[#D5D5D5] rounded-xl px-3.5 py-2.5 text-sm focus:outline-none focus:border-[#1E1E1E]"
                  placeholder="ejemplo@correo.com"
                  required
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-[#202020] mb-1.5">Contraseña</label>
                <input
                  type="password"
                  value={loginPass}
                  onChange={(e) => setLoginPass(e.target.value)}
                  className="w-full bg-[#F8F8F8] border border-[#D5D5D5] rounded-xl px-3.5 py-2.5 text-sm focus:outline-none focus:border-[#1E1E1E]"
                  placeholder="••••••••"
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
                  ¿No tienes cuenta? <span className="underline">Registrarte aquí</span>
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
                    placeholder="José"
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
                    placeholder="Escobedo"
                    required
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-[#202020] mb-1">Correo electrónico</label>
                <input
                  type="email"
                  value={regEmail}
                  onChange={(e) => setRegEmail(e.target.value)}
                  className="w-full bg-[#F8F8F8] border border-[#D5D5D5] rounded-xl px-3 py-2 text-sm focus:outline-none focus:border-[#1E1E1E]"
                  placeholder="productor@correo.com"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-[#202020] mb-1">Número telefónico (10 dígitos)</label>
                <input
                  type="tel"
                  value={regPhone}
                  onChange={(e) => setRegPhone(e.target.value)}
                  className="w-full bg-[#F8F8F8] border border-[#D5D5D5] rounded-xl px-3 py-2 text-sm focus:outline-none focus:border-[#1E1E1E]"
                  placeholder="8441234567"
                  required
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-[#202020] mb-1">Contraseña</label>
                  <input
                    type="password"
                    value={regPassword}
                    onChange={(e) => setRegPassword(e.target.value)}
                    className="w-full bg-[#F8F8F8] border border-[#D5D5D5] rounded-xl px-3 py-2 text-sm focus:outline-none focus:border-[#1E1E1E]"
                    placeholder="Mínimo 6 caracteres"
                    required
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-[#202020] mb-1">Confirmar contraseña</label>
                  <input
                    type="password"
                    value={regConfirmPass}
                    onChange={(e) => setRegConfirmPass(e.target.value)}
                    className="w-full bg-[#F8F8F8] border border-[#D5D5D5] rounded-xl px-3 py-2 text-sm focus:outline-none focus:border-[#1E1E1E]"
                    placeholder="Repite la contraseña"
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
                  ¿Ya tienes cuenta? <span className="underline">Iniciar sesión</span>
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    );
  }

  // ============================================================================
  // DEFINICIÓN DE LOS 5 ICONOS DEL MENÚ LATERAL (CUADROS GRISES -> NEGROS)
  // ============================================================================
  const navItems: { id: typeof activeTab; icon: React.ElementType; label: string }[] = [
    { id: 'home', icon: Home, label: 'Inicio' },
    { id: 'telemetry', icon: Activity, label: 'Valores en vivo' },
    { id: 'crops', icon: Sprout, label: 'Cultivos aptos' },
    { id: 'sensors', icon: Cpu, label: 'Estado de los sensores' },
    { id: 'advice', icon: ClipboardCheck, label: 'Recomendaciones' },
  ];

  // ============================================================================
  // PANEL PRINCIPAL POST-LOGIN
  // ============================================================================
  return (
    <div className="min-h-screen bg-[#EEEEEE] text-[#202020] flex flex-col font-sans">
      {/* BARRA SUPERIOR LIMPIA: Logo a la izquierda y Batería pequeña a la derecha */}
      <header className="h-16 bg-white border-b border-[#D5D5D5] px-5 flex items-center justify-between sticky top-0 z-30">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-[#1E1E1E] text-white flex items-center justify-center">
            <Sprout className="w-5 h-5 text-[#F39200]" />
          </div>
          <span className="font-bold text-base tracking-tight text-[#202020]">AgroStake</span>
        </div>

        <div className="flex items-center gap-3">
          <MinimalBatteryStatus batteryV={latest.battery_v} />
          <button
            onClick={() => setUser(null)}
            className="w-9 h-9 rounded-xl bg-[#E2E2E2] hover:bg-[#1E1E1E] text-[#202020] hover:text-white flex items-center justify-center transition-colors cursor-pointer"
            title="Cerrar sesión"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </header>

      {/* CUERPO CON BARRA LATERAL ARRIBA A LA IZQUIERDA Y CONTENIDO INDEPENDIENTE */}
      <div className="flex-1 flex">
        {/* SIDEBAR COMPACTO ALINEADO ARRIBA (SIN BAJAR MUCHO) */}
        <aside className="w-20 bg-white border-r border-[#D5D5D5] flex flex-col items-center justify-start pt-5 gap-3 sticky top-16 h-[calc(100vh-4rem)] shrink-0">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isSelected = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setActiveTab(item.id)}
                title={item.label}
                className={`w-12 h-12 rounded-xl flex items-center justify-center transition-all cursor-pointer ${
                  isSelected
                    ? 'bg-[#1E1E1E] text-white shadow-sm'
                    : 'bg-[#E2E2E2] text-[#202020] hover:bg-[#1E1E1E] hover:text-white'
                }`}
              >
                <Icon className="w-5 h-5 stroke-[2]" />
              </button>
            );
          })}
        </aside>

        {/* CONTENEDOR CENTRAL POR VISTA */}
        <main className="flex-1 p-6 md:p-8 max-w-5xl mx-auto w-full">
          {/* ==================================================================
              VISTA 1: INICIO (CASA) - FOTO DE ESTACA, GUÍA SENCILLA E INICIAR ANÁLISIS
             ================================================================== */}
          {activeTab === 'home' && (
            <section className="bg-white border border-[#D5D5D5] rounded-2xl p-6 md:p-8 shadow-sm">
              <div className="max-w-2xl mx-auto text-center mb-6">
                <span className="inline-block text-[11px] font-bold uppercase tracking-wider text-[#F39200] bg-[#F39200]/10 px-3 py-1 rounded-full mb-2">
                  Guía de uso rápido
                </span>
                <h1 className="text-2xl md:text-3xl font-bold text-[#202020] tracking-tight">
                  Conoce el estado de tu tierra antes de sembrar
                </h1>
                <p className="text-sm text-[#777777] mt-2 leading-relaxed">
                  La estaca revisa la humedad y la temperatura directamente en la zona donde crecen las raíces, ayudándote a elegir el mejor cultivo y saber cuándo regar.
                </p>
              </div>

              {/* Imagen limpia de la estaca */}
              <div className="max-w-lg mx-auto mb-8">
                <StakePhotoDisplay />
              </div>

              {/* Paso a paso sencillo y formal para el agricultor */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
                <div className="bg-[#F8F8F8] border border-[#E5E5E5] rounded-xl p-4">
                  <div className="w-7 h-7 rounded-lg bg-[#1E1E1E] text-white text-xs font-bold flex items-center justify-center mb-2.5">
                    1
                  </div>
                  <h3 className="text-sm font-bold text-[#202020] mb-1">Coloca la estaca en el terreno</h3>
                  <p className="text-xs text-[#777777] leading-relaxed">
                    Entiérrala de forma vertical en el lugar donde planeas sembrar, procurando que las puntas metálicas entren completas en la tierra húmeda.
                  </p>
                </div>

                <div className="bg-[#F8F8F8] border border-[#E5E5E5] rounded-xl p-4">
                  <div className="w-7 h-7 rounded-lg bg-[#1E1E1E] text-white text-xs font-bold flex items-center justify-center mb-2.5">
                    2
                  </div>
                  <h3 className="text-sm font-bold text-[#202020] mb-1">Enciende e inicia la lectura</h3>
                  <p className="text-xs text-[#777777] leading-relaxed">
                    Presiona el botón naranja de abajo para que la estaca mida las condiciones actuales del suelo y las envíe a tu pantalla.
                  </p>
                </div>

                <div className="bg-[#F8F8F8] border border-[#E5E5E5] rounded-xl p-4">
                  <div className="w-7 h-7 rounded-lg bg-[#1E1E1E] text-white text-xs font-bold flex items-center justify-center mb-2.5">
                    3
                  </div>
                  <h3 className="text-sm font-bold text-[#202020] mb-1">Revisa qué sembrar y cómo cuidar</h3>
                  <p className="text-xs text-[#777777] leading-relaxed">
                    Consulta en los iconos de la izquierda qué semillas se adaptan mejor a tu tierra hoy y qué ajustes sencillos puedes aplicar.
                  </p>
                </div>
              </div>

              {/* Botón de Iniciar Análisis con animación y salto automático a Valores en vivo */}
              <div className="flex flex-col items-center">
                <button
                  onClick={triggerStartAnalysis}
                  disabled={isAnalyzing}
                  className="inline-flex items-center gap-3 px-8 py-4 rounded-xl bg-[#F39200] hover:bg-[#e08600] disabled:opacity-80 text-[#1E1E1E] font-bold text-sm shadow-sm transition-all cursor-pointer"
                >
                  {isAnalyzing ? (
                    <>
                      <Loader2 className="w-5 h-5 animate-spin" />
                      <span>Analizando terreno...</span>
                    </>
                  ) : (
                    <>
                      <Play className="w-5 h-5 fill-current" />
                      <span>Iniciar análisis</span>
                    </>
                  )}
                </button>

                {isAnalyzing && (
                  <div className="mt-4 w-full max-w-md bg-[#F8F8F8] border border-[#DEDEDE] rounded-xl p-3 text-center">
                    <p className="text-xs font-semibold text-[#202020]">{analysisStepText}</p>
                    <div className="w-full h-1.5 bg-[#DEDEDE] rounded-full overflow-hidden mt-2">
                      <div className="h-full bg-[#F39200] animate-pulse w-4/5 rounded-full" />
                    </div>
                  </div>
                )}
              </div>
            </section>
          )}

          {/* ==================================================================
              VISTA 2: VALORES EN VIVO (TIEMPO REAL + PAUSA AL CONFIGURAR)
             ================================================================== */}
          {activeTab === 'telemetry' && (
            <section className="space-y-6">
              {/* Encabezado y controles de tiempo */}
              <div className="bg-white border border-[#D5D5D5] rounded-2xl p-6 flex flex-wrap items-center justify-between gap-4">
                <div>
                  <h2 className="text-xl font-bold text-[#202020]">Valores en vivo</h2>
                  <p className="text-xs text-[#777777] mt-0.5">
                    {isConfiguringTime
                      ? 'Lectura en pausa mientras eliges el tiempo de actualización.'
                      : `Actualizando automáticamente cada ${sampleIntervalSec} segundos.`}
                  </p>
                </div>

                {/* Controles de tiempo real y botón que pausa al configurar */}
                <div className="flex flex-wrap items-center gap-2">
                  <select
                    value={soilTexture}
                    onChange={(e) => setSoilTexture(e.target.value as SoilTextureCode)}
                    className="bg-[#F8F8F8] border border-[#D5D5D5] rounded-xl px-3 py-2 text-xs font-semibold text-[#202020] focus:outline-none"
                    title="Tipo de tierra (FAO-56)"
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
                      <span>Tiempo: {sampleIntervalSec}s (Configurar)</span>
                    </button>
                  ) : (
                    <div className="flex items-center gap-1.5 bg-[#F8F8F8] border border-[#F39200] rounded-xl p-1">
                      <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-[#E9A11B] px-2">
                        <Pause className="w-3 h-3" /> En pausa:
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

              {/* 4 Tarjetas de las variables de la base de datos v3.3 */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                <div className="bg-white border border-[#D5D5D5] rounded-2xl p-5">
                  <div className="flex items-center justify-between text-xs font-semibold text-[#777777] mb-2">
                    <span>Temperatura</span>
                    <Thermometer className="w-4 h-4 text-[#F39200]" />
                  </div>
                  <div className="flex items-baseline gap-1">
                    <span className="text-3xl font-bold text-[#202020] tabular-nums">
                      {latest.soil_temperature_c.toFixed(1)}
                    </span>
                    <span className="text-sm font-semibold text-[#777777]">°C</span>
                  </div>
                  <span className="inline-block mt-3 text-[11px] font-semibold text-[#159447]">
                    Lectura directa en raíz
                  </span>
                </div>

                <div className="bg-white border border-[#D5D5D5] rounded-2xl p-5">
                  <div className="flex items-center justify-between text-xs font-semibold text-[#777777] mb-2">
                    <span>Humedad</span>
                    <Droplets className="w-4 h-4 text-[#202020]" />
                  </div>
                  <div className="flex items-baseline gap-1">
                    <span className="text-3xl font-bold text-[#202020] tabular-nums">
                      {latest.soil_moisture_pct.toFixed(1)}
                    </span>
                    <span className="text-sm font-semibold text-[#777777]">%</span>
                  </div>
                  <span className="inline-block mt-3 text-[11px] font-semibold text-[#777777]">
                    Suelo {SOIL_TEXTURES[soilTexture].name_es}
                  </span>
                </div>

                <div className="bg-white border border-[#D5D5D5] rounded-2xl p-5">
                  <div className="flex items-center justify-between text-xs font-semibold text-[#777777] mb-2">
                    <span>Nivel de pH</span>
                    <FlaskConical className="w-4 h-4 text-[#F39200]" />
                  </div>
                  <div className="flex items-baseline gap-1">
                    <span className="text-3xl font-bold text-[#202020] tabular-nums">
                      {latest.soil_ph.toFixed(2)}
                    </span>
                    <span className="text-sm font-semibold text-[#777777]">pH</span>
                  </div>
                  <span className="inline-block mt-3 text-[11px] font-semibold text-[#159447]">
                    Rango equilibrado: 5.8 – 7.0
                  </span>
                </div>

                <div className="bg-white border border-[#D5D5D5] rounded-2xl p-5">
                  <div className="flex items-center justify-between text-xs font-semibold text-[#777777] mb-2">
                    <span>Precipitación (30d)</span>
                    <CloudRain className="w-4 h-4 text-[#202020]" />
                  </div>
                  <div className="flex items-baseline gap-1">
                    <span className="text-3xl font-bold text-[#202020] tabular-nums">
                      {latest.precip_total_mm.toFixed(1)}
                    </span>
                    <span className="text-sm font-semibold text-[#777777]">mm</span>
                  </div>
                  <span className="inline-block mt-3 text-[11px] font-semibold text-[#777777]">
                    Acumulado climático
                  </span>
                </div>
              </div>

              {/* Gráfica limpia exclusiva de Temperatura y Humedad */}
              <div className="bg-white border border-[#D5D5D5] rounded-2xl p-6">
                <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
                  <div>
                    <h3 className="text-sm font-bold text-[#202020]">Comportamiento de Temperatura y Humedad</h3>
                    <p className="text-xs text-[#777777]">Registro continuo en tiempo real ({history.length} muestras recientes)</p>
                  </div>
                  <div className="flex items-center gap-4 text-xs font-semibold">
                    <span className="flex items-center gap-1.5">
                      <span className="w-3 h-1 bg-[#F39200] rounded-full inline-block" /> Temperatura (°C)
                    </span>
                    <span className="flex items-center gap-1.5">
                      <span className="w-3 h-1 bg-[#1E1E1E] rounded-full inline-block" /> Humedad (%)
                    </span>
                  </div>
                </div>

                <div className="h-60 w-full bg-[#F8F8F8] border border-[#E5E5E5] rounded-xl p-4">
                  <svg viewBox="0 0 600 180" className="w-full h-full overflow-visible">
                    {[0, 45, 90, 135, 180].map((y) => (
                      <line key={y} x1="0" y1={y} x2="600" y2={y} stroke="#E2E2E2" strokeDasharray="3 3" />
                    ))}
                    {/* Línea de Humedad (%) */}
                    <polyline
                      fill="none"
                      stroke="#1E1E1E"
                      strokeWidth="2.5"
                      points={history
                        .map((pt, i) => {
                          const x = (i / Math.max(1, history.length - 1)) * 600;
                          const y = 170 - ((pt.soil_moisture_pct - 5) / 45) * 150;
                          return `${x},${Math.min(175, Math.max(5, y))}`;
                        })
                        .join(' ')}
                    />
                    {/* Línea de Temperatura (°C) */}
                    <polyline
                      fill="none"
                      stroke="#F39200"
                      strokeWidth="2.8"
                      points={history
                        .map((pt, i) => {
                          const x = (i / Math.max(1, history.length - 1)) * 600;
                          const y = 170 - ((pt.soil_temperature_c - 5) / 35) * 150;
                          return `${x},${Math.min(175, Math.max(5, y))}`;
                        })
                        .join(' ')}
                    />
                  </svg>
                </div>
              </div>
            </section>
          )}

          {/* ==================================================================
              VISTA 3: CULTIVOS APTOS (6 CULTIVOS DEL SQL + REGLA 4/4 + SCORE)
             ================================================================== */}
          {activeTab === 'crops' && (
            <section className="space-y-4">
              <div className="bg-white border border-[#D5D5D5] rounded-2xl p-6">
                <h2 className="text-xl font-bold text-[#202020]">Cultivos aptos</h2>
                <p className="text-xs text-[#777777] mt-1">
                  Compatibilidad calculada con las 4 variables del terreno (Temperatura, Humedad según textura {SOIL_TEXTURES[soilTexture].name_es}, pH y Lluvia a 30 días).
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {evaluatedCrops.map(({ crop, checks, variables_ok, classification, ml_suitability_score }) => {
                  const isExpanded = expandedCropId === crop.id;
                  const statusBadge =
                    classification === 'recomendado'
                      ? { text: 'Recomendado', bg: 'bg-[#159447]/15 text-[#159447]' }
                      : classification === 'condicionado'
                      ? { text: 'Recomendado con condiciones', bg: 'bg-[#E9A11B]/15 text-[#E9A11B]' }
                      : { text: 'No recomendado actualmente', bg: 'bg-[#E34545]/15 text-[#E34545]' };

                  return (
                    <article
                      key={crop.id}
                      className="bg-white border border-[#D5D5D5] rounded-2xl overflow-hidden shadow-sm flex flex-col"
                    >
                      <div className="h-36 w-full bg-[#F8F8F8] relative overflow-hidden">
                        <img src={crop.image} alt={crop.common_name_es} className="w-full h-full object-cover" />
                        <div className="absolute top-3 right-3 bg-[#1E1E1E] text-white text-xs font-bold px-3 py-1 rounded-full">
                          {ml_suitability_score}% compatible
                        </div>
                      </div>

                      <div className="p-5 flex-1 flex flex-col justify-between">
                        <div>
                          <div className="flex items-center justify-between gap-2 mb-2">
                            <div>
                              <h3 className="text-base font-bold text-[#202020]">{crop.common_name_es}</h3>
                              <span className="text-xs italic text-[#777777]">{crop.scientific_name}</span>
                            </div>
                            <span className={`text-[11px] font-bold px-2.5 py-1 rounded-full ${statusBadge.bg}`}>
                              {statusBadge.text}
                            </span>
                          </div>

                          <p className="text-xs text-[#555555] mb-3">
                            Ciclo estimado: <strong>{crop.cycle_days_min} a {crop.cycle_days_max} días</strong> · {crop.harvest_notes}
                          </p>
                        </div>

                        <div>
                          <button
                            onClick={() => setExpandedCropId(isExpanded ? null : crop.id)}
                            className="w-full py-2 px-3 rounded-xl bg-[#F8F8F8] hover:bg-[#EEEEEE] border border-[#E5E5E5] flex items-center justify-between text-xs font-semibold text-[#202020] cursor-pointer"
                          >
                            <span>Ver desglose ({variables_ok} de 4 condiciones cumplidas)</span>
                            {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                          </button>

                          {isExpanded && (
                            <div className="mt-3 pt-3 border-t border-[#EEEEEE] space-y-2">
                              {checks.map((chk) => (
                                <div key={chk.variable} className="bg-[#F8F8F8] rounded-xl p-2.5 text-xs">
                                  <div className="flex items-center justify-between font-semibold">
                                    <span>{chk.label} (Ideal: {chk.range})</span>
                                    <span
                                      className={
                                        chk.status === 'in_range' ? 'text-[#159447]' : 'text-[#E34545]'
                                      }
                                    >
                                      Actual: {chk.val}
                                    </span>
                                  </div>
                                  {chk.advice && (
                                    <p className="text-[11px] text-[#777777] mt-1">{chk.advice}</p>
                                  )}
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
                    </article>
                  );
                })}
              </div>
            </section>
          )}

          {/* ==================================================================
              VISTA 4: ESTADO DE LOS SENSORES
             ================================================================== */}
          {activeTab === 'sensors' && (
            <section className="space-y-4">
              <div className="bg-white border border-[#D5D5D5] rounded-2xl p-6 flex items-center justify-between">
                <div>
                  <h2 className="text-xl font-bold text-[#202020]">Estado de los sensores</h2>
                  <p className="text-xs text-[#777777] mt-0.5">4 de 4 canales operativos en la parcela</p>
                </div>
                <span className="inline-flex items-center gap-2 text-xs font-bold text-[#159447] bg-[#159447]/10 px-3 py-1.5 rounded-full">
                  <ShieldCheck className="w-4 h-4" /> En línea
                </span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {[
                  {
                    name: 'Sensor de Temperatura (DS18B20)',
                    reading: `${latest.soil_temperature_c.toFixed(1)} °C`,
                    comm: 'Conectado · Lectura estable en raíz',
                    status: 'ok',
                  },
                  {
                    name: 'Sensor de Humedad Capacitivo',
                    reading: `${latest.soil_moisture_pct.toFixed(1)} %`,
                    comm: 'Conectado · Calibrado para suelo ' + SOIL_TEXTURES[soilTexture].name_es,
                    status: 'ok',
                  },
                  {
                    name: 'Canal de Nivel de pH',
                    reading: `${latest.soil_ph.toFixed(2)} pH`,
                    comm: 'Activo · Monitoreo químico del terreno',
                    status: 'ok',
                  },
                  {
                    name: 'Canal de Precipitación (NASA POWER)',
                    reading: `${latest.precip_total_mm.toFixed(1)} mm (30 días)`,
                    comm: 'Sincronizado · Serie MERRA-2 PRECTOTCORR',
                    status: 'ok',
                  },
                ].map((s, idx) => (
                  <div key={idx} className="bg-white border border-[#D5D5D5] rounded-2xl p-5 flex items-start justify-between gap-4">
                    <div>
                      <div className="flex items-center gap-2 mb-1">
                        <span className="w-2.5 h-2.5 rounded-full bg-[#159447]" />
                        <h3 className="text-sm font-bold text-[#202020]">{s.name}</h3>
                      </div>
                      <p className="text-xs text-[#777777] mb-3">{s.comm}</p>
                      <span className="text-xs font-semibold text-[#202020] bg-[#F8F8F8] border border-[#E5E5E5] px-2.5 py-1 rounded-lg">
                        Última lectura: {s.reading} ({latest.timeLabel})
                      </span>
                    </div>
                    <Radio className="w-5 h-5 text-[#159447] shrink-0" />
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* ==================================================================
              VISTA 5: RECOMENDACIONES (REGLAS OFICIALES advice_rules DEL SQL)
             ================================================================== */}
          {activeTab === 'advice' && (
            <section className="space-y-4">
              <div className="bg-white border border-[#D5D5D5] rounded-2xl p-6">
                <h2 className="text-xl font-bold text-[#202020]">Recomendaciones para cuidar el suelo</h2>
                <p className="text-xs text-[#777777] mt-0.5">
                  Acciones concretas generadas a partir de las lecturas actuales de tu parcela.
                </p>
              </div>

              <div className="space-y-3">
                {(() => {
                  const items: { priority: 'Alta' | 'Media' | 'Baja'; title: string; detail: string; metric: string }[] = [];
                  const moistTarget = computeFao56MoistureRange(0.5, soilTexture);

                  if (latest.soil_moisture_pct < moistTarget.minPct) {
                    items.push({
                      priority: 'Alta',
                      title: 'Aplicar riego de apoyo en la parcela',
                      detail: formatAdviceRule('soil_moisture', 'below', latest.soil_moisture_pct, moistTarget.minPct),
                      metric: `Humedad actual: ${latest.soil_moisture_pct.toFixed(1)}%`,
                    });
                  } else if (latest.soil_moisture_pct > moistTarget.maxPct) {
                    items.push({
                      priority: 'Alta',
                      title: 'Pausar riegos y vigilar el drenaje',
                      detail: formatAdviceRule('soil_moisture', 'above', latest.soil_moisture_pct, moistTarget.maxPct),
                      metric: `Humedad actual: ${latest.soil_moisture_pct.toFixed(1)}%`,
                    });
                  } else {
                    items.push({
                      priority: 'Baja',
                      title: 'Humedad en nivel adecuado',
                      detail: `El suelo conserva ${latest.soil_moisture_pct.toFixed(1)}% de humedad, dentro del rango ideal (${moistTarget.minPct}% a ${moistTarget.maxPct}%) para tierra ${SOIL_TEXTURES[soilTexture].name_es}. Mantén el calendario actual sin regar de más.`,
                      metric: 'Humedad en rango',
                    });
                  }

                  if (latest.soil_ph < 5.8) {
                    items.push({
                      priority: 'Media',
                      title: 'Corregir acidez del terreno',
                      detail: formatAdviceRule('soil_ph', 'below', latest.soil_ph, 6.2),
                      metric: `pH actual: ${latest.soil_ph.toFixed(2)}`,
                    });
                  } else if (latest.soil_ph > 7.2) {
                    items.push({
                      priority: 'Media',
                      title: 'Reducir alcalinidad del suelo',
                      detail: formatAdviceRule('soil_ph', 'above', latest.soil_ph, 6.8),
                      metric: `pH actual: ${latest.soil_ph.toFixed(2)}`,
                    });
                  } else {
                    items.push({
                      priority: 'Baja',
                      title: 'Nivel de pH equilibrado para absorción de nutrientes',
                      detail: `Con un pH de ${latest.soil_ph.toFixed(2)}, las raíces pueden aprovechar correctamente los nutrientes naturales de la tierra sin requerir correctores químicos.`,
                      metric: `pH actual: ${latest.soil_ph.toFixed(2)}`,
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

      {/* BURBUJA DE CHAT IA FLOTANTE EN ESQUINA INFERIOR DERECHA */}
      <AgroAssistantBubble latest={latest} texture={soilTexture} />
    </div>
  );
}

export default App;