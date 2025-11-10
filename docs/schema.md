# Graph Schema – Course Prerequisite System

This document defines the graph data model used in the Neo4j-based course prerequisite planning system.

## Node Types

### Course

Represents a university course.

| Property  | Type    | Description                            |
|-----------|---------|----------------------------------------|
| code      | String  | Unique course code (e.g., "CS101")     |
| title     | String  | Full course title                      |
| credits   | Integer | Number of credit hours                 |
| level     | Integer | Course level (e.g., 100, 200, etc.)    |

### PrerequisiteGroup

Represents a group of prerequisite courses associated with a Course.

| Property     | Type            | Description                                                       |
|--------------|------------------|-------------------------------------------------------------------|
| id           | UUID            | Unique identifier for the group                                   |
| type         | String          | Logical connector: "AND", "OR", or "CUSTOM"                       |
| recommended  | Boolean / Null  | true = recommended, false = required, null = custom/unspecified   |

## Relationship Types

### (:Course)-[:REQUIRES]->(:PrerequisiteGroup)

Defines that a Course requires a specific PrerequisiteGroup.

### (:PrerequisiteGroup)-[:HAS]->(:Course)

Connects the PrerequisiteGroup to one or more Courses which serve as the prerequisites.

## Example Structure

Course `CS201` requires both `CS101` and `MATH100` (AND), and recommends either `BIO101` or `BIO102` (OR).

Structure:

(:Course {code: "CS201"})
    ├──[:REQUIRES]──> (:PrerequisiteGroup {type: "AND", recommended: false})
    │                      ├──[:HAS]──> (:Course {code: "CS101"})
    │                      └──[:HAS]──> (:Course {code: "MATH100"})
    └──[:REQUIRES]──> (:PrerequisiteGroup {type: "OR", recommended: true})
                           ├──[:HAS]──> (:Course {code: "BIO101"})
                           └──[:HAS]──> (:Course {code: "BIO102"})
