using System;
using System.Collections.Generic;
using System.Linq;
using System.Linq.Expressions;
using System.Threading.Tasks;
using Microsoft.EntityFrameworkCore;
using Fuzzbin.Core.Entities;
using Fuzzbin.Core.Interfaces;
using Fuzzbin.Core.Specifications;
using Fuzzbin.Data.Context;
using Fuzzbin.Data.Specifications;

namespace Fuzzbin.Data.Repositories
{
    public class Repository<T> : IRepository<T> where T : BaseEntity
    {
        protected readonly ApplicationDbContext _context;
        protected readonly DbSet<T> _dbSet;

        public Repository(ApplicationDbContext context)
        {
            _context = context;
            _dbSet = context.Set<T>();
        }

        public async Task<T?> GetByIdAsync(Guid id)
        {
            return await _dbSet.FindAsync(id);
        }

        public async Task<IEnumerable<T>> GetAllAsync()
        {
            return await _dbSet
                .Where(e => e.IsActive)
                .AsNoTracking()
                .ToListAsync();
        }

        public async Task<IEnumerable<T>> GetAllAsync(bool includeDeleted)
        {
            if (includeDeleted)
            {
                return await _dbSet
                    .AsNoTracking()
                    .ToListAsync();
            }
            return await _dbSet
                .Where(e => e.IsActive)
                .AsNoTracking()
                .ToListAsync();
        }

        public async Task<IEnumerable<T>> GetAsync(Expression<Func<T, bool>> predicate)
        {
            return await _dbSet
                .Where(predicate)
                .Where(e => e.IsActive)
                .AsNoTracking()
                .ToListAsync();
        }

        public IQueryable<T> GetQueryable()
        {
            return _dbSet
                .Where(e => e.IsActive)
                .AsNoTracking()
                .AsQueryable();
        }

        public async Task<IReadOnlyList<T>> ListAsync(ISpecification<T> specification)
        {
            if (specification == null)
            {
                throw new ArgumentNullException(nameof(specification));
            }

            var queryable = SpecificationEvaluator<T>.GetQuery(_dbSet.AsQueryable(), specification);
            return await queryable.ToListAsync();
        }

        public async Task<T?> FirstOrDefaultAsync(ISpecification<T> specification)
        {
            if (specification == null)
            {
                throw new ArgumentNullException(nameof(specification));
            }

            var queryable = SpecificationEvaluator<T>.GetQuery(_dbSet.AsQueryable(), specification);
            return await queryable.FirstOrDefaultAsync();
        }

        public async Task<int> CountAsync(ISpecification<T> specification)
        {
            if (specification == null)
            {
                throw new ArgumentNullException(nameof(specification));
            }

            var queryable = SpecificationEvaluator<T>.GetQuery(_dbSet.AsQueryable(), specification, ignoreIncludes: true, applyOrder: false);
            return await queryable.CountAsync();
        }

        public async Task<T> AddAsync(T entity)
        {
            await _dbSet.AddAsync(entity);
            return entity;
        }

        public async Task<IEnumerable<T>> AddRangeAsync(IEnumerable<T> entities)
        {
            var entityList = entities.ToList();
            await _dbSet.AddRangeAsync(entityList);
            return entityList;
        }

        public Task UpdateAsync(T entity)
        {
            AttachOrUpdateEntity(entity);
            return Task.CompletedTask;
        }

        public Task UpdateRangeAsync(IEnumerable<T> entities)
        {
            foreach (var entity in entities)
            {
                AttachOrUpdateEntity(entity);
            }
            return Task.CompletedTask;
        }

        public Task DeleteAsync(T entity)
        {
            // Soft delete
            entity.IsActive = false;
            AttachOrUpdateEntity(entity);
            return Task.CompletedTask;
        }

        public Task DeleteRangeAsync(IEnumerable<T> entities)
        {
            // Soft delete
            foreach (var entity in entities)
            {
                entity.IsActive = false;
            }
            foreach (var entity in entities)
            {
                AttachOrUpdateEntity(entity);
            }
            return Task.CompletedTask;
        }

        public async Task DeleteByIdAsync(Guid id)
        {
            var entity = await GetByIdAsync(id);
            if (entity != null)
            {
                await DeleteAsync(entity);
            }
        }

        public async Task<bool> ExistsAsync(Expression<Func<T, bool>> predicate)
        {
            return await _dbSet.AnyAsync(predicate);
        }

        public async Task<int> CountAsync(Expression<Func<T, bool>>? predicate = null)
        {
            if (predicate == null)
            {
                return await _dbSet.Where(e => e.IsActive).CountAsync();
            }
            return await _dbSet.Where(predicate).Where(e => e.IsActive).CountAsync();
        }

        public async Task<T?> FirstOrDefaultAsync(Expression<Func<T, bool>> predicate)
        {
            return await _dbSet
                .Where(predicate)
                .Where(e => e.IsActive)
                .AsNoTracking()
                .FirstOrDefaultAsync();
        }

        public async Task<int> SaveChangesAsync()
        {
            return await _context.SaveChangesAsync();
        }

        private void AttachOrUpdateEntity(T entity)
        {
            var trackedEntry = _context.ChangeTracker.Entries<T>()
                .FirstOrDefault(entry => entry.Entity.Id == entity.Id);

            if (trackedEntry is not null)
            {
                trackedEntry.CurrentValues.SetValues(entity);
                trackedEntry.State = Microsoft.EntityFrameworkCore.EntityState.Modified;
            }
            else
            {
                _dbSet.Update(entity);
            }
        }
    }
}
