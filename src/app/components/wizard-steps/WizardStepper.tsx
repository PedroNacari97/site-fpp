import React from 'react';
import { Check } from 'lucide-react';
import { StepId } from './types';

const STEPS = [
  { id: 1, title: 'Cliente & Programa' },
  { id: 2, title: 'Voo de Ida' },
  { id: 3, title: 'Voo de Volta' },
  { id: 4, title: 'Passageiros' },
  { id: 5, title: 'Valores' },
  { id: 6, title: 'Revisão' },
] as const;

interface Props {
  currentStep: StepId;
  onStepClick: (id: StepId) => void;
}

export const WizardStepper: React.FC<Props> = ({ currentStep, onStepClick }) => (
  <div className='grid grid-cols-6 gap-2'>
    {STEPS.map((step, idx) => {
      const isComplete = step.id < currentStep;
      const isCurrent = step.id === currentStep;
      const blocked = step.id > currentStep;
      return (
        <button key={step.id} type='button' disabled={blocked} onClick={() => onStepClick(step.id as StepId)} className='flex flex-col items-center gap-2'>
          <div className={`w-10 h-10 rounded-full flex items-center justify-center transition ${isComplete ? 'bg-green-500' : isCurrent ? 'bg-blue-600 ring-4 ring-blue-500/30' : 'bg-gray-700 text-gray-400'}`}>
            {isComplete ? <Check size={16} /> : step.id}
          </div>
          <span className={`${isCurrent || isComplete ? 'text-white' : 'text-gray-500'} text-xs`}>{step.title}</span>
          {idx < 5 && <span className={`hidden md:block h-[2px] w-full ${step.id < currentStep ? 'bg-green-500' : 'bg-gray-700'}`} />}
        </button>
      );
    })}
  </div>
);
