import { useMemo } from 'react';
import { EmissionData, StepId } from '../components/wizard-steps/types';
import { validateStep } from '../utils/emissionValidation';

export const useEmissionValidation = (step: StepId, data: EmissionData) => {
  const errors = useMemo(() => validateStep(data, step), [data, step]);
  const isValid = Object.keys(errors).length === 0;
  return { errors, isValid };
};
