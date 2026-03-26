import React from 'react';
import { StepProps } from './types';

export const StepValores: React.FC<StepProps> = ({ data, errors, onUpdate }) => {
  const valores = data.valores;
  const update = (patch: Partial<typeof valores>) => onUpdate({ valores: { ...valores, ...patch } });

  return (
    <div className='space-y-4'>
      <h2 className='text-2xl font-semibold text-white'>Valores e Financeiro</h2>
      <div className='grid md:grid-cols-2 gap-3'>
        <input className='input' type='number' placeholder='Quantidade de milhas' value={valores.quantidadeMilhas || ''} onChange={(e) => update({ quantidadeMilhas: Number(e.target.value) })} />
        <input className='input' type='number' step='0.01' placeholder='Custo por milheiro' value={valores.custoMilhas || ''} onChange={(e) => update({ custoMilhas: Number(e.target.value) })} />
        <input className='input' type='number' step='0.01' placeholder='Taxas' value={valores.taxas || ''} onChange={(e) => update({ taxas: Number(e.target.value) })} />
        <input className='input opacity-70' disabled value={valores.valorMilheiros.toFixed(2)} />
      </div>
      {(errors.quantidadeMilhas || errors.custoMilhas || errors.taxas) && <p className='text-red-400 text-sm'>{errors.quantidadeMilhas || errors.custoMilhas || errors.taxas}</p>}

      <div className='grid md:grid-cols-2 gap-3'>
        <input className='input opacity-70' disabled value={valores.valorFinalCliente.toFixed(2)} />
        <input className='input' type='number' step='0.01' placeholder='Valor Total Final' value={valores.valorTotalFinal || ''} onChange={(e) => update({ valorTotalFinal: Number(e.target.value) })} />
        <input className='input' type='number' step='0.01' placeholder='Valor de Referência' value={valores.valorReferencia || ''} onChange={(e) => update({ valorReferencia: Number(e.target.value) })} />
      </div>
      {errors.valorTotalFinal && <p className='text-red-400 text-sm'>{errors.valorTotalFinal}</p>}

      <div className='grid md:grid-cols-2 gap-3'>
        <div className={`rounded-xl p-4 border ${valores.lucro >= 0 ? 'border-green-500/30 bg-green-900/20' : 'border-red-500/30 bg-red-900/20'}`}>
          <p className='text-sm text-gray-300'>Lucro Estimado</p>
          <p className='text-3xl font-semibold text-white'>R$ {valores.lucro.toFixed(2)}</p>
          <p className='text-sm text-gray-300'>{valores.margemPercentual.toFixed(1)}% de margem</p>
        </div>
        <div className='rounded-xl p-4 border border-blue-500/30 bg-blue-900/20'>
          <p className='text-sm text-gray-300'>Economia do Cliente</p>
          <p className='text-3xl font-semibold text-blue-300'>R$ {valores.economiaObtida.toFixed(2)}</p>
          <p className='text-sm text-gray-300'>{valores.economiaPercentual.toFixed(1)}% de desconto</p>
        </div>
      </div>

      <div className='grid md:grid-cols-2 gap-3'>
        <input className='input uppercase' maxLength={6} placeholder='Localizador' value={data.localizador} onChange={(e) => onUpdate({ localizador: e.target.value.toUpperCase() })} />
        <textarea className='input h-24' placeholder='Observações' value={data.observacoes} onChange={(e) => onUpdate({ observacoes: e.target.value })} />
      </div>
      {errors.localizador && <p className='text-red-400 text-sm'>{errors.localizador}</p>}
    </div>
  );
};
