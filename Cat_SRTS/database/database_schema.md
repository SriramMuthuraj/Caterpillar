# CAT_SRTS MongoDB Database Schema

## Database

`smart_rental_tracking_system`

## Collections

### `equipment`

Purpose: Stores the master list of Caterpillar equipment tracked by the rental system.

Primary identifier: `equipmentId`

Fields:

- `_id`: MongoDB document identifier.
- `equipmentId`: Unique equipment identifier.
- `equipmentName`: Equipment model/name.
- `category`: Equipment type such as Excavator, Dozer, Wheel Loader, or Motor Grader.
- `manufacturer`: Equipment manufacturer.
- `horsePower`: Machine horsepower.
- `ownershipStatus`: `Rented` or `Owned`.
- `lastUsedDate`: Most recent usage date.
- `expectedReturnDate`: Expected return date for rented equipment, if applicable.
- `currentStatus`: `Available`, `Assigned`, `Working`, `Idle`, or `Returned`.
- `createdAt`: Creation timestamp.
- `updatedAt`: Last update timestamp.

Indexes:

- `equipmentId_unique`: unique index on `equipmentId`.
- `currentStatus_idx`: index on `currentStatus`.
- `ownershipStatus_idx`: index on `ownershipStatus`.

### `operators`

Purpose: Stores equipment operator information and current equipment assignment references.

Primary identifier: `operatorId`

Fields:

- `_id`: MongoDB document identifier.
- `operatorId`: Unique operator identifier.
- `operatorName`: Operator full name.
- `licenseNumber`: Heavy-equipment license number.
- `phoneNumber`: Operator phone number.
- `assignedEquipmentId`: Equipment currently assigned to the operator, if any.
- `createdAt`: Creation timestamp.
- `updatedAt`: Last update timestamp.

Indexes:

- `operatorId_unique`: unique index on `operatorId`.
- `assignedEquipmentId_idx`: index on `assignedEquipmentId`.

### `assignments`

Purpose: Tracks equipment checkout/check-in assignments between equipment, operators, and work sites.

Primary identifier: `assignmentId`

Fields:

- `_id`: MongoDB document identifier.
- `assignmentId`: Unique assignment identifier.
- `equipmentId`: Referenced equipment identifier.
- `operatorId`: Referenced operator identifier.
- `siteName`: Site where the equipment is assigned.
- `checkOutTime`: Assignment checkout timestamp.
- `checkInTime`: Assignment check-in timestamp, if returned.
- `status`: Assignment status such as `Assigned`, `Working`, `Idle`, or `Returned`.
- `createdAt`: Creation timestamp.
- `updatedAt`: Last update timestamp.

Indexes:

- `assignmentId_unique`: unique index on `assignmentId`.
- `assignment_equipmentId_idx`: index on `equipmentId`.
- `assignment_operatorId_idx`: index on `operatorId`.
- `assignment_status_idx`: index on `status`.

### `usage_logs`

Purpose: Stores daily/periodic equipment usage metrics for runtime, fuel use, idle time, and location.

Primary identifier: `usageId`

Fields:

- `_id`: MongoDB document identifier.
- `usageId`: Unique usage log identifier.
- `equipmentId`: Referenced equipment identifier.
- `operatorId`: Referenced operator identifier.
- `runtimeHours`: Number of operating hours.
- `fuelUsage`: Fuel consumed for the usage period.
- `idleHours`: Idle hours for the usage period.
- `location`: Site/location where the usage occurred.
- `usageDate`: Usage date.
- `createdAt`: Creation timestamp.

Indexes:

- `usage_equipmentId_idx`: index on `equipmentId`.
- `usage_operatorId_idx`: index on `operatorId`.
- `usageDate_idx`: index on `usageDate`.

## Relationships

- `assignments.equipmentId` references `equipment.equipmentId`.
- `assignments.operatorId` references `operators.operatorId`.
- `usage_logs.equipmentId` references `equipment.equipmentId`.
- `usage_logs.operatorId` references `operators.operatorId`.
- `operators.assignedEquipmentId` references `equipment.equipmentId` when present.

