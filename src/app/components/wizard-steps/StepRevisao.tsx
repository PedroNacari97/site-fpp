import React from 'react';
import { Loader2 } from 'lucide-react';
import { EmissionData } from './types';

interface Props {
  data: EmissionData;
  loading: boolean;
  onEdit: (step: number) => void;
  onFinish: () => void;
}

export const StepRevisao: React.FC<Props> = ({ data, loading, onEdit, onFinish }) => {
  return (
    <div className='space-y-6'>
      <h2 className='text-2xl font-semibold text-gray-900'>Revisão Final</h2>

      <div className='bg-white border border-gray-200 rounded-xl shadow-sm p-4 space-y-3'>
        <p className='text-lg font-medium text-gray-900'>Cliente & Programa</p>
        <p className='text-sm text-gray-500'>{data.clienteId} • {data.programaId}</p>
        <button type='button' onClick={() => onEdit(1)} className='h-10 px-4 rounded-lg border border-gray-300 text-sm transition-all duration-200 hover:shadow-md active:scale-95'>Editar</button>
      </div>

      <div className='bg-white border border-gray-200 rounded-xl shadow-sm p-4 space-y-3'>
        <p className='text-lg font-medium text-gray-900'>Voos</p>
        <p className='text-sm text-gray-500'>Ida: {data.vooIda.origem} → {data.vooIda.destino}</p>
        <button type='button' onClick={() => onEdit(2)} className='h-10 px-4 rounded-lg border border-gray-300 text-sm transition-all duration-200 hover:shadow-md active:scale-95'>Editar</button>
      </div>

      <div className='bg-white border border-gray-200 rounded-xl shadow-sm p-4 space-y-3'>
        <p className='text-lg font-medium text-gray-900'>Passageiros</p>
        <p className='text-sm text-gray-500'>{data.passageiros.length} pessoa(s)</p>
        <button type='button' onClick={() => onEdit(4)} className='h-10 px-4 rounded-lg border border-gray-300 text-sm transition-all duration-200 hover:shadow-md active:scale-95'>Editar</button>
      </div>

      <div className='bg-green-50 border border-green-500 rounded-xl p-4 text-sm text-green-700'>Pronto para finalizar!</div>

      <button
        type='button'
        onClick={onFinish}
        disabled={loading}
        className='bg-blue-600 text-white h-10 px-4 rounded-lg text-sm transition-all duration-200 hover:bg-blue-700 hover:shadow-md active:scale-95 disabled:bg-gray-300 disabled:cursor-not-allowed w-full inline-flex items-center justify-center gap-2'
      >
        {loading ? <><Loader2 size={16} className='animate-spin' /> Salvando...</> : 'Finalizar Emissão'}
      </button>
    </div>
  );
};
