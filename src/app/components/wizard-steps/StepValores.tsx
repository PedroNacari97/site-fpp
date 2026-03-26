import React from 'react';
import { StepProps } from './types';

const inputClass = 'h-10 w-full rounded-lg border border-gray-300 text-sm px-3 focus:ring-2 focus:ring-blue-500 outline-none';

export const StepValores: React.FC<StepProps> = ({ data, errors, onUpdate }) => {
  const valores = data.valores;
  const update = (patch: Partial<typeof valores>) => onUpdate({ valores: { ...valores, ...patch } });

  return (
    <div className='space-y-6'>
      <h2 className='text-2xl font-semibold text-gray-900'>Valores e Financeiro</h2>

      <div className='bg-white border border-gray-200 rounded-xl shadow-sm p-4 space-y-4'>
        <h3 className='text-lg font-medium text-gray-900'>Custos Operacionais</h3>
        <div className='grid grid-cols-1 md:grid-cols-2 gap-4'>
          <input className={`${inputClass} ${errors.quantidadeMilhas ? 'border-red-500' : ''}`} type='number' placeholder='Quantidade de Milhas' value={valores.quantidadeMilhas || ''} onChange={(e) => update({ quantidadeMilhas: Number(e.target.value) })} />
          <input className={`${inputClass} ${errors.custoMilhas ? 'border-red-500' : ''}`} type='number' step='0.01' placeholder='Custo por Milheiro' value={valores.custoMilhas || ''} onChange={(e) => update({ custoMilhas: Number(e.target.value) })} />
          <input className={`${inputClass} ${errors.taxas ? 'border-red-500' : ''}`} type='number' step='0.01' placeholder='Taxas' value={valores.taxas || ''} onChange={(e) => update({ taxas: Number(e.target.value) })} />
          <input className={`${inputClass} bg-gray-100`} value={valores.valorMilheiros.toFixed(2)} disabled />
        </div>
      </div>

      <div className='bg-white border border-gray-200 rounded-xl shadow-sm p-4 space-y-4'>
        <h3 className='text-lg font-medium text-gray-900'>Precificação</h3>
        <div className='grid grid-cols-1 md:grid-cols-2 gap-4'>
          <input className={`${inputClass} bg-gray-100`} value={valores.valorFinalCliente.toFixed(2)} disabled />
          <input className={`${inputClass} ${errors.valorTotalFinal ? 'border-red-500' : ''}`} type='number' step='0.01' placeholder='Valor Total Final' value={valores.valorTotalFinal || ''} onChange={(e) => update({ valorTotalFinal: Number(e.target.value) })} />
          <input className={inputClass} type='number' step='0.01' placeholder='Valor de Referência' value={valores.valorReferencia || ''} onChange={(e) => update({ valorReferencia: Number(e.target.value) })} />
        </div>
      </div>

      <div className='grid grid-cols-1 md:grid-cols-2 gap-4'>
        <div className='bg-white border border-gray-200 rounded-xl shadow-sm p-4'>
          <p className='text-sm font-medium text-gray-900'>Lucro Estimado</p>
          <p className={`text-2xl font-semibold ${valores.lucro >= 0 ? 'text-green-500' : 'text-red-500'}`}>R$ {valores.lucro.toFixed(2)}</p>
        </div>
        <div className='bg-white border border-gray-200 rounded-xl shadow-sm p-4'>
          <p className='text-sm font-medium text-gray-900'>Economia do Cliente</p>
          <p className='text-2xl font-semibold text-blue-600'>R$ {valores.economiaObtida.toFixed(2)}</p>
        </div>
      </div>

      <div className='grid grid-cols-1 md:grid-cols-2 gap-4'>
        <input className={`${inputClass} ${errors.localizador ? 'border-red-500' : ''}`} maxLength={6} placeholder='Localizador' value={data.localizador} onChange={(e) => onUpdate({ localizador: e.target.value.toUpperCase() })} />
        <textarea className='w-full rounded-lg border border-gray-300 text-sm px-3 py-2 focus:ring-2 focus:ring-blue-500 outline-none' placeholder='Observações' value={data.observacoes} onChange={(e) => onUpdate({ observacoes: e.target.value })} />
      </div>

      {(errors.quantidadeMilhas || errors.custoMilhas || errors.taxas || errors.valorTotalFinal || errors.localizador) && (
        <p className='text-xs text-red-500'>
          {errors.quantidadeMilhas || errors.custoMilhas || errors.taxas || errors.valorTotalFinal || errors.localizador}
        </p>
      )}
    </div>
  );
};
