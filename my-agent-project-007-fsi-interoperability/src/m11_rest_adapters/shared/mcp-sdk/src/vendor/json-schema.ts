/**
 * Minimal JSON Schema 7 type shim — avoids a separate `@types/json-schema`
 * dependency. Only the shape zodToJsonSchema returns is needed.
 */

export type JSONSchema7TypeName =
  | "string"
  | "number"
  | "integer"
  | "boolean"
  | "object"
  | "array"
  | "null";

export interface JSONSchema7 {
  $id?: string;
  $schema?: string;
  $ref?: string;
  title?: string;
  description?: string;
  type?: JSONSchema7TypeName | JSONSchema7TypeName[];
  properties?: { [key: string]: JSONSchema7 };
  required?: string[];
  items?: JSONSchema7 | JSONSchema7[];
  additionalProperties?: boolean | JSONSchema7;
  enum?: unknown[];
  const?: unknown;
  format?: string;
  pattern?: string;
  minLength?: number;
  maxLength?: number;
  minimum?: number;
  maximum?: number;
  minItems?: number;
  maxItems?: number;
  oneOf?: JSONSchema7[];
  anyOf?: JSONSchema7[];
  allOf?: JSONSchema7[];
  not?: JSONSchema7;
  default?: unknown;
  [k: string]: unknown;
}
