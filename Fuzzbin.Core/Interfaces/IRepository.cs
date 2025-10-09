using System;
using System.Collections.Generic;
using System.Linq;
using System.Linq.Expressions;
using System.Threading.Tasks;
using Fuzzbin.Core.Entities;
using Fuzzbin.Core.Specifications;

namespace Fuzzbin.Core.Interfaces
{
    /// <summary>
    /// Generic repository interface for data access
    /// </summary>
    /// <typeparam name="T">Entity type</typeparam>
    public interface IRepository<T> where T : BaseEntity
    {
        /// <summary>
        /// Get entity by ID
        /// </summary>
        Task<T?> GetByIdAsync(Guid id);

        /// <summary>
        /// Get all entities
        /// </summary>
        Task<IEnumerable<T>> GetAllAsync();

        /// <summary>
        /// Get all entities with optional include deleted
        /// </summary>
        Task<IEnumerable<T>> GetAllAsync(bool includeDeleted);

        /// <summary>
        /// Get entities matching a predicate
        /// </summary>
        Task<IEnumerable<T>> GetAsync(Expression<Func<T, bool>> predicate);

        /// <summary>
        /// Get a queryable for complex queries
        /// </summary>
        IQueryable<T> GetQueryable();

        /// <summary>
        /// Executes a specification and returns the matching entities.
        /// </summary>
        Task<IReadOnlyList<T>> ListAsync(ISpecification<T> specification);

        /// <summary>
        /// Returns the first entity that matches the specification or null.
        /// </summary>
        Task<T?> FirstOrDefaultAsync(ISpecification<T> specification);

        /// <summary>
        /// Returns the count of entities matching the specification.
        /// </summary>
        Task<int> CountAsync(ISpecification<T> specification);

        /// <summary>
        /// Add a new entity
        /// </summary>
        Task<T> AddAsync(T entity);

        /// <summary>
        /// Add multiple entities
        /// </summary>
        Task<IEnumerable<T>> AddRangeAsync(IEnumerable<T> entities);

        /// <summary>
        /// Update an entity
        /// </summary>
        Task UpdateAsync(T entity);

        /// <summary>
        /// Update multiple entities
        /// </summary>
        Task UpdateRangeAsync(IEnumerable<T> entities);

        /// <summary>
        /// Delete an entity
        /// </summary>
        Task DeleteAsync(T entity);

        /// <summary>
        /// Delete multiple entities
        /// </summary>
        Task DeleteRangeAsync(IEnumerable<T> entities);

        /// <summary>
        /// Delete by ID
        /// </summary>
        Task DeleteByIdAsync(Guid id);

        /// <summary>
        /// Check if entity exists
        /// </summary>
        Task<bool> ExistsAsync(Expression<Func<T, bool>> predicate);

        /// <summary>
        /// Get count of entities
        /// </summary>
        Task<int> CountAsync(Expression<Func<T, bool>>? predicate = null);

        /// <summary>
        /// Get first entity matching predicate
        /// </summary>
        Task<T?> FirstOrDefaultAsync(Expression<Func<T, bool>> predicate);

        /// <summary>
        /// Save changes to database
        /// </summary>
        Task<int> SaveChangesAsync();
    }
}
